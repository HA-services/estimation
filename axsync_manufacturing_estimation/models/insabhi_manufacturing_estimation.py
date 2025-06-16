from odoo import models, fields, api


class InsabhiManufacturingEstimation(models.Model):
    _name = "insabhi.manufacturing.estimation"
    _description = 'Insabhi Manufacturing Estimation'

    name = fields.Char(string="Sequence", default=lambda self: self.env['ir.sequence'].next_by_code('mrp.est.seq'),
                       required=True, readonly=True)
    display_name = fields.Text(string='Name')
    product_ids = fields.One2many(
        'insabhi.manufacturing.estimation.product',
        'estimation_id',
        string="Products")
    estimation_line_ids = fields.One2many(
        'insabhi.manufacturing.estimation.line',
        'estimation_id',
        string="Estimation Lines"
    )

    @api.onchange('product_ids')
    def _onchange_product_ids(self):
        new_lines = self._update_estimation_lines()
        self.estimation_line_ids = [(5, 0, 0)] + new_lines

    def _update_estimation_lines(self):
        """
        Update estimation_line_ids with recalculated needed, status, and available_char.
        """
        if not self.product_ids:
            return []

        new_lines = []
        processed_keys = set()
        processed_product_names = set()
        processed_product_codes = set()
        processed_product_quantity = set()
        raw_material_usage = {}
        code = 1

        for product in self.product_ids.filtered(lambda obj:obj.is_active):
            bom = self.env['mrp.bom'].search([
                ('product_tmpl_id', 'in', product.product_id.product_tmpl_id.ids),
                ('active', '=', True)
            ], limit=1)

            code_value = f'P{code}'
            product_name = product.product_id.display_name
            product_quantity = product.quantity
            product_name_with_qty = f'{product_name} ({product.product_id.qty_available})'

            if not bom:
                # Add line for product with no BoM
                new_lines.append((0, 0, {
                    'product_code': code_value,
                    'product_name': product_name_with_qty,
                    'product_id': product.product_id.id,
                    'raw_material': False,
                    'partner_id': False,
                    'cost': 0.0,
                    'quantity': product_quantity,
                    'quantity_char': str(product_quantity),
                    'needed': 0.0,
                    'needed_char': str(0.0),
                    'available': 0.0,
                    'available_char': str(0.0),
                    'status': 'nobom',
                    'status_icon': '⚠️',
                    'right_now_available': 0.0,
                }))
                code += 1
                continue  # Skip further processing

            for idx, bom_line in enumerate(bom.bom_line_ids):
                raw_material = bom_line.product_id
                key = (product.product_id.id, raw_material.id)
                if key in processed_keys:
                    continue  # Skip duplicates
                processed_keys.add(key)
                quantity = product.quantity
                needed_qty = bom_line.product_qty * quantity
                available_qty = raw_material.qty_available

                if raw_material.id not in raw_material_usage:
                    raw_material_usage[raw_material.id] = {
                        'prior_needed': 0,
                        'prior_products': []
                    }

                prior_needed = raw_material_usage[raw_material.id]['prior_needed']
                remaining_qty = available_qty - prior_needed  # Available after prior needs
                right_now_available = remaining_qty - needed_qty  # Available after current needs

                if prior_needed > 0 and raw_material_usage[raw_material.id]['prior_products']:
                    used_by = raw_material_usage[raw_material.id]['prior_products']
                    used_by_str = ", ".join(used_by)
                    if len(used_by) > 1:
                        last_comma = used_by_str.rfind(',')
                        used_by_str = used_by_str[:last_comma] + ' and' + used_by_str[last_comma + 1:]
                    # available_char = f"{available_qty} (used by {used_by_str})"
                    # needed_char = f"{needed_qty} (used by {used_by_str})"
                    available_char = f"{available_qty}"
                    needed_char = f"{needed_qty}"
                else:
                    available_char = str(available_qty)
                    needed_char = str(needed_qty)

                code_value = f'P{code}'

                raw_material_usage[raw_material.id]['prior_needed'] += needed_qty
                if needed_qty > 0 and code_value not in raw_material_usage[raw_material.id]['prior_products']:
                    raw_material_usage[raw_material.id]['prior_products'].append(code_value)

                product_name = product.product_id.display_name if product.product_id.display_name not in processed_product_names else False
                product_code = code_value if code_value not in processed_product_codes else False
                product_name_with_qty = f'{product_name} ({product.product_id.qty_available})' if product_name else ''
                product_quantity = quantity if product.product_id.display_name not in processed_product_names else False
                status = 'pass' if remaining_qty >= needed_qty else 'fail'
                status_icon = '✅' if status == 'pass' else '❌'

                new_lines.append((0, 0, {
                    'product_code': product_code,
                    'product_name': product_name_with_qty,
                    'product_id': product.product_id.id,
                    'raw_material': raw_material.id,
                    'partner_id': raw_material.seller_ids[0].partner_id.id if raw_material.seller_ids else False,
                    'cost': raw_material.standard_price,
                    'quantity': product_quantity,
                    'quantity_char': str(product_quantity) if product_quantity else "",
                    'needed': needed_qty,
                    'needed_char': needed_char,
                    'available': available_qty,
                    'available_char': available_char,
                    'status': status,
                    'status_icon': status_icon,
                    'right_now_available': right_now_available,
                }))

                if product.product_id.display_name not in processed_product_names:
                    processed_product_names.add(product.product_id.display_name)
                    processed_product_quantity.add(quantity)
                if code_value not in processed_product_codes:
                    processed_product_codes.add(code_value)
            code += 1

        return new_lines

    # def action_reload(self):
    #     new_lines = self._update_estimation_lines()
    #     self.estimation_line_ids = [(5, 0, 0)] + new_lines

    def write(self, vals):
        res = super().write(vals)
        if vals.get('product_ids'):
            for rec in self:
                rec.estimation_line_ids.unlink()
                new_lines = rec._update_estimation_lines()
                rec.write({'estimation_line_ids': new_lines})
        return res


class InsabhiManufacturingEstimationLine(models.Model):
    _name = "insabhi.manufacturing.estimation.line"
    _description = 'Insabhi Manufacturing Estimation Line'

    estimation_id = fields.Many2one('insabhi.manufacturing.estimation',string="Estimation")
    product_id = fields.Many2one('product.product', string='Product')
    product_name = fields.Char(string='Product')
    product_code = fields.Char(string='Code')
    raw_material = fields.Many2one('product.product', string='Raw Material')
    cost = fields.Float(string='Cost', digits=(16, 4))
    quantity = fields.Float(string='Quantity', compute="_compute_quantity", store=True, digits=(16, 4))
    quantity_char = fields.Char(string='Quantity', default='1.0')
    needed = fields.Float(string='Needed', digits=(16, 4))
    needed_char = fields.Char(string='Needed')
    available = fields.Float(string='On Hand', digits=(16, 4))
    available_char = fields.Char(string='On Hand')
    status = fields.Selection(selection=[("pass", "Pass"), ("fail", "Fail"), ("nobom", "No BoM")])
    status_icon = fields.Char(string="Status")
    right_now_available = fields.Float(string='Remaining', digits=(16, 4))
    partner_id = fields.Many2one('res.partner', string='Vendor')

    @api.depends('estimation_id.product_ids.quantity')
    def _compute_quantity(self):
        for rec in self.estimation_id.product_ids:
            bom = self.env['mrp.bom'].search([
                ('product_tmpl_id', 'in', rec.product_id.product_tmpl_id.ids),
                ('active', '=', True)
            ], limit=1)

            if not bom:
                continue

            quantity = rec.quantity
            for idx, bom_line in enumerate(bom.bom_line_ids):
                for line in rec.estimation_id.estimation_line_ids:
                    if line.product_id.id == rec.product_id.id:
                        line.quantity = quantity
                        line.needed = bom_line.product_qty * line.quantity

    def action_open_product(self):
        action = self.env["ir.actions.actions"]._for_xml_id("stock.stock_product_normal_action")
        action_id = action['id']
        return {
            'type': 'ir.actions.act_url',
            'url': f'/odoo/action-{action_id}/{self.product_id.id}',
        }


class InsabhiManufacturingEstimationProduct(models.Model):
    _name = "insabhi.manufacturing.estimation.product"
    _description = 'Insabhi Manufacturing Estimation Product'

    estimation_id = fields.Many2one('insabhi.manufacturing.estimation', string='Product')
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float(string='Quantity', default=1.0, digits=(16, 4))
    is_active = fields.Boolean(string='Active', default=True)