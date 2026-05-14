# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_whatsapp_orderable = fields.Boolean(
        string='WhatsApp Orderable',
        default=False,
        help='Only products with this flag can be ordered from WhatsApp customer flow.',
    )
