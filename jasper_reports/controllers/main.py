# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (C) 2019-Today Serpent Consulting Services Pvt. Ltd.
#                         (<http://www.serpentcs.com>)
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# guarantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import json
import logging
import datetime

from odoo.addons.web.controllers import main as report
from odoo.http import content_disposition, route, request, serialize_exception as _serialize_exception
from werkzeug.urls import url_decode
from odoo.tools import html_escape
from odoo.tools.safe_eval import safe_eval, time

_logger = logging.getLogger(__name__)


class ReportController(report.ReportController):

    @route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        if converter == 'jasper':
            report_jas = request.env[
                'ir.actions.report']._get_report_from_name(reportname)
            context = dict(request.env.context)
            if docids:
                docids = [int(i) for i in docids.split(',')]
            if data.get('options'):
                data.update(json.loads(data.pop('options')))
            if data.get('context'):
                # Ignore 'lang' here, because the context in data is the one
                # from the webclient *but* if the user explicitely wants to
                # change the lang, this mechanism overwrites it.
                data['context'] = json.loads(data['context'])
                if data['context'].get('lang'):
                    del data['context']['lang']
                context.update(data['context'])
            # Get the report and output type
            jasper, output_type = report_jas.with_context(
                context).render_jasper(docids, data=data)
            report_name = str(report_jas.name) + '.' + output_type
            content_dict = {
                'pdf': 'application/pdf',
                'html': 'application/html',
                'csv': 'text/csv',
                'xls': 'application/xls',
                'rtf': 'application/octet-stream',
                'odt': 'application/vnd.oasis.opendocument.text',
                'ods': 'application/vnd.oasis.opendocument.spreadsheet',
                'txt': 'text/plain',
            }
            pdfhttpheaders = [
                ('Content-Type', content_dict.get(output_type)),
                ('Content-Length', len(jasper))
            ]
            return request.make_response(jasper, headers=pdfhttpheaders)
        return super(ReportController, self).report_routes(
            reportname, docids, converter, **data)

    @route()
    def report_download(self, data, token, context=None):
        """This function is used by 'action_manager_report.js' in order to trigger the download of
        a pdf/controller report.

        :param data: a javascript array JSON.stringified containg report internal url ([0]) and
        type [1]
        :returns: Response with a filetoken cookie and an attachment header
        """
        requestcontent = json.loads(data)
        url, type = requestcontent[0], requestcontent[1]
        if type == 'jasper':
            try:
                converter = 'jasper'
                extension = 'pdf'
                pattern = '/report/jasper/'
                _logger.info("Requested url: {}".format(url))
                reportname = url.split(pattern)[1].split('?')[0]

                docids = None
                _logger.info("report name : {}".format(reportname))
                if '/' in reportname:
                    reportname, docids = reportname.split('/')

                if docids:
                    # Generic report:
                    _logger.info("generating generic report docid = {}".format(docids))
                    response = self.report_routes(reportname, docids=docids, converter=converter, context=context)
                else:
                    # Particular report:
                    _logger.info("generating particular report")
                    data = dict(url_decode(url.split('?')[1]).items())  # decoding the args represented in JSON
                    if 'context' in data:
                        context, data_context = json.loads(context or '{}'), json.loads(data.pop('context'))
                        context = json.dumps({**context, **data_context})
                    response = self.report_routes(reportname, converter=converter, context=context, **data)

                report = request.env['ir.actions.report']._get_report_from_name(reportname)
                # Get report extension
                extension = report.jasper_output
                # Get report model
                model = report.model_id.model
                # Search document name from given ID
                doc_name = request.env[model].search([('id', '=', docids)]).name
                filename = "{}_{}_{}.{}".format(report.name, doc_name,
                                                datetime.datetime.today().strftime('%Y-%m-%d'), extension)

                if docids:
                    ids = [int(x) for x in docids.split(",")]
                    obj = request.env[report.model].browse(ids)
                    if report.print_report_name and not len(obj) > 1:
                        report_name = safe_eval(report.print_report_name, {'object': obj, 'time': time})
                        filename = "%s.%s" % (report_name, extension)
                response.headers.add('Content-Disposition', content_disposition(filename))
                response.set_cookie('fileToken', token)
                return response
            except Exception as e:
                se = _serialize_exception(e)
                error = {
                    'code': 200,
                    'message': "Odoo Server Error",
                    'data': se
                }
                return request.make_response(html_escape(json.dumps(error)))
        else:
            return super(ReportController, self).report_download(data, token, context)
