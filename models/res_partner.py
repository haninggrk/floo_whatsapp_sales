# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    wa_shipping_address = fields.Text(
        string='WhatsApp Shipping Address',
        help='Required free-text shipping address for WhatsApp order checkout.',
    )
