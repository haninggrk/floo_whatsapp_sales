# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    floo_wa_webhook_url = fields.Char(
        string='WhatsApp Node Webhook URL',
        config_parameter='floo_whatsapp_sales.webhook_url',
        help='Node.js endpoint for Odoo->WhatsApp event notifications.',
    )

    floo_wa_delivery_timezone = fields.Char(
        string='Delivery Notification Timezone',
        config_parameter='floo_whatsapp_sales.delivery_timezone',
        default='Asia/Jakarta',
        help='Timezone for morning delivery notification scheduling.',
    )

    floo_wa_delivery_notify_hour = fields.Integer(
        string='Delivery Notification Hour',
        config_parameter='floo_whatsapp_sales.delivery_notify_hour',
        default=8,
        help='Local hour (0-23) when delivery-day morning message is sent.',
    )
