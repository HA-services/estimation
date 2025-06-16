import io
import xlsxwriter
from odoo import http
from odoo.http import request


class EstimationExcelReport(http.Controller):

    @http.route('/report/estimation/crossed-lines', type='http', auth='user')
    def export_crossed_estimation_lines(self, **kwargs):
        estimation = request.env['insabhi.manufacturing.estimation'].browse(int(kwargs.get('estimation_id')))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Manufacturing Estimation")

        headers = ['Code', 'Product', 'Quantity', 'Raw Material', 'Vendor', 'Cost', 'Needed', 'Right Now', 'On Hand',
                   'Status']
        bold = workbook.add_format({'bold': True})
        bold_h1 = workbook.add_format({'bold': True, 'font_size': 16})
        qty_format = workbook.add_format({'num_format': '0.0000', 'align': 'right'})

        row = 0

        # H1-style header
        title = f"{estimation.name}        Name: {estimation.display_name}"
        sheet.merge_range(row, 0, row, len(headers) - 1, title, bold_h1)
        sheet.set_row(row, 25)
        row += 2

        # Write table headers (start at row 3)
        for col, header in enumerate(headers):
            sheet.write(row, col, header, bold)

        # Data rows
        row += 1
        written_products = set()
        col_widths = [len(h) for h in headers]

        for line in estimation.estimation_line_ids.filtered(lambda l: l.status == 'fail'):
            product_id = line.product_id.id

            if product_id not in written_products:
                product_code = next((c.product_code for c in
                                     estimation.estimation_line_ids.filtered(lambda pc: pc.product_id.id == product_id)
                                     if c.product_code), None)
                product_name = next((n.product_name for n in
                                     estimation.estimation_line_ids.filtered(lambda pn: pn.product_id.id == product_id)
                                     if n.product_name), None)
                product_quantity = next((q.quantity for q in estimation.estimation_line_ids.filtered(
                    lambda pn: pn.product_id.id == product_id) if q.quantity), None)
                written_products.add(product_id)
            else:
                product_code = ''
                product_name = ''
                product_quantity = ''

            row_data = [
                product_code,
                product_name,
                product_quantity,
                line.raw_material.display_name if line.raw_material else '',
                line.raw_material.seller_ids[
                    0].partner_id.name if line.raw_material and line.raw_material.seller_ids else '',
                line.raw_material.standard_price if line.raw_material else 0.0,
                line.needed_char or 0.0,
                line.right_now_available or 0.0,
                line.available or 0.0,
                '❌'
            ]

            for col, value in enumerate(row_data):
                # Write formatted numbers for decimals
                if col in [2, 5, 7, 8] and isinstance(value, (int, float)):
                    sheet.write(row, col, value, qty_format)
                    val_str = f"{value:.4f}"
                else:
                    sheet.write(row, col, value)
                    val_str = str(value)

                # Track max column width needed
                if len(val_str) > col_widths[col]:
                    col_widths[col] = len(val_str)

            row += 1

        # Adjust column widths
        for i, width in enumerate(col_widths):
            sheet.set_column(i, i, max(width + 2, 12) if i in [2, 5, 7, 8] else width + 2)

        workbook.close()
        output.seek(0)

        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename=Manufacturing Estimation.xlsx')
            ]
        )

