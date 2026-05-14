# -*- coding: utf-8 -*-
from odoo import models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def write(self, vals):
        previous_states = {tx.id: tx.state for tx in self}
        result = super().write(vals)

        if 'state' in vals:
            processed_orders = set()
            for tx in self:
                if previous_states.get(tx.id) == 'done' or tx.state != 'done':
                    continue

                related_orders = tx.sale_order_ids
                if not related_orders and tx.invoice_ids:
                    related_orders = tx.invoice_ids.mapped('invoice_line_ids.sale_line_ids.order_id')

                for order in related_orders:
                    if order.id in processed_orders:
                        continue
                    processed_orders.add(order.id)
                    self.env['sale.order'].sudo().wa_process_paid_order(order.id, tx.reference or '')

        return result
