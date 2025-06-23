from odoo import models, fields, api, _


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
    summary_lines = fields.One2many('insabhi.manufacturing.estimation.summary', 'estimation_id', string="Total Needed", compute='_compute_summary_lines', store=True)
    purchase_order_ids = fields.Many2many('purchase.order', string="Purchase Orders", compute='_compute_purchase_order_ids', readonly=True, store=False)
    purchase_order_count = fields.Integer('Purchase order count', compute='_compute_purchase_order_ids')
    sale_id = fields.Many2one('sale.order', string='Reference', readonly=True)

    @api.depends('estimation_line_ids')
    def _compute_purchase_order_ids(self):
        for rec in self:
            purchase_order_ids = self.env['purchase.order'].sudo().search([('estimation_id', '=', rec.id)])
            rec.purchase_order_ids = [(6, 0, purchase_order_ids.ids)]
            rec.purchase_order_count = len(purchase_order_ids)

    @api.depends('estimation_line_ids')
    def _compute_summary_lines(self):
        for record in self:
            summary_vals = {}
            for line in record.estimation_line_ids.filtered(lambda l: l.status == 'fail'):
                key = (line.raw_material.id, line.partner_id.id)
                if key not in summary_vals:
                    summary_vals[key] = {
                        'raw_material': line.raw_material.id,
                        'partner_id': line.partner_id.id,
                        'cost': 0.0,
                        'needed': 0.0,
                        'right_now': 0.0,
                    }
                summary_vals[key]['cost'] += line.cost or 0.0
                summary_vals[key]['needed'] += line.needed or 0.0
                summary_vals[key]['right_now'] += line.right_now_available or 0.0

            result = [(5, 0, 0)]
            for val in summary_vals.values():
                result.append((0, 0, val))
            record.summary_lines = result

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

    def action_create_po(self):
        PO = self.env['purchase.order']
        notification_msg = ""

        for summary in self.summary_lines.filtered(lambda obj: obj.is_create_po):
            if not summary.raw_material or not summary.partner_id:
                continue  # Skip incomplete lines

            order_line_vals = {
                'product_id': summary.raw_material.id,
                'name': summary.raw_material.name,
                'price_unit': summary.cost,
                'product_qty': summary.needed,
            }

            po_order = PO.search([
                ('estimation_id', '=', self.id),
                ('partner_id', '=', summary.partner_id.id),
                ('state', 'in', ['draft', 'sent'])
            ], limit=1)

            if not po_order:
                new_po = PO.create({
                    'partner_id': summary.partner_id.id,
                    'estimation_id': self.id,
                    'order_line': [(0, 0, order_line_vals)],
                })
                notification_msg = f"PO created successfully"
            else:
                existing_line = po_order.order_line.filtered(lambda l: l.product_id == summary.raw_material)
                if existing_line:
                    existing_line.write({
                        'price_unit': summary.cost,
                        'product_qty': summary.needed,
                        'name': summary.raw_material.name,
                    })
                    notification_msg = f"PO updated successfully"
                else:
                    po_order.write({
                        'order_line': [(0, 0, order_line_vals)],
                    })
                    notification_msg = f"Added line successfully"

        notif_message = notification_msg if notification_msg else _("Please select the 'Create PO' checkbox")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if notification_msg else 'warning',
                'title': _("Purchase Order Update"),
                'message': notif_message,
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_view_po(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.purchase_form_action")
        action['domain'] = [('id', 'in', self.mapped('purchase_order_ids.id'))]
        action['context'] = dict(self._context, create=False)
        return action

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
    quantity = fields.Float(string='Quantity', digits=(16, 4))
    quantity_char = fields.Char(string='Quantity', default='1.0')
    needed = fields.Float(string='Needed', digits=(16, 4))
    needed_char = fields.Char(string='Needed')
    available = fields.Float(string='On Hand', digits=(16, 4))
    available_char = fields.Char(string='On Hand')
    status = fields.Selection(selection=[("pass", "Pass"), ("fail", "Fail"), ("nobom", "No BoM")])
    status_icon = fields.Char(string="Status")
    right_now_available = fields.Float(string='Remaining', digits=(16, 4))
    partner_id = fields.Many2one('res.partner', string='Vendor')

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


class EstimationSummary(models.Model):
    _name = 'insabhi.manufacturing.estimation.summary'
    _description = 'Summary Line (Total Needed)'

    estimation_id = fields.Many2one('insabhi.manufacturing.estimation')
    raw_material = fields.Many2one('product.product', string="Raw Material")
    partner_id = fields.Many2one('res.partner', string="Vendor")
    cost = fields.Float(string='Cost', digits=(16, 4))
    needed = fields.Float(string='Needed', digits=(16, 4))
    right_now = fields.Float(string='Remaining', digits=(16, 4))
    is_create_po = fields.Boolean(string='Create PO')


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    estimation_id = fields.Many2one('insabhi.manufacturing.estimation', copy=False)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    estimation_id = fields.Many2one('insabhi.manufacturing.estimation', string='Estimation', copy=False)
    estimation_order_ids = fields.Many2many('purchase.order', string="Estimation Orders",compute='_compute_estimation_order_ids', readonly=True, store=False)
    estimation_order_count = fields.Integer('Estimation order count', compute='_compute_estimation_order_ids')

    @api.depends('estimation_id')
    def _compute_estimation_order_ids(self):
        for rec in self:
            estimation_order_ids = self.env['insabhi.manufacturing.estimation'].sudo().search([('sale_id', '=', rec.id)])
            rec.estimation_order_ids = [(6, 0, estimation_order_ids.ids)]
            rec.estimation_order_count = len(estimation_order_ids)

    def action_create_estimation(self):
        data = []
        skipped_lines = []
        if self.order_line:
            for line in self.order_line:
                if line.product_id:
                    if line.product_id.virtual_available < line.product_uom_qty:
                        data.append((0, 0, {
                            'product_id': line.product_id.id,
                            'quantity': line.product_uom_qty,
                            'is_active': True,
                        }))
                    else:
                        skipped_lines.append(line.product_id.display_name)

            if not data:
                message_type = "warning"
                message = _("All products have sufficient forecasted stock.")
            else:
                if not self.estimation_id:
                    # Create new estimation
                    estimation = self.env['insabhi.manufacturing.estimation'].create({
                        'display_name': f"Created from {self.name}",
                        'sale_id': self.id,
                        'product_ids': data,
                    })
                    self.estimation_id = estimation.id
                    estimation._onchange_product_ids()
                    message = _("Estimation created from Sale Order %s.") % self.name
                else:
                    # Update existing estimation
                    self.estimation_id.product_ids.unlink()
                    self.estimation_id.write({'product_ids': data})
                    self.estimation_id._onchange_product_ids()
                    message = _("Estimation updated for Sale Order %s.") % self.name

                if skipped_lines:
                    pass
                    # message += "\n\n" + _("Skipped lines (sufficient stock):") + "\n- " + "\n- ".join(skipped_lines)
                message_type = "success"
        else:
            message_type = "warning"
            message = _("Please add a line before estimation.")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': message_type,
                'title': _("Estimation Update"),
                'message': message,
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_view_estimation(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("axsync_manufacturing_estimation.action_new_project")
        action['domain'] = [('id', 'in', self.mapped('estimation_order_ids.id'))]
        action['context'] = dict(self._context, create=False)
        return action
