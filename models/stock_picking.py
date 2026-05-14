# -*- coding: utf-8 -*-
import uuid
from datetime import datetime

import pytz

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = ['stock.picking', 'floo.whatsapp.webhook.mixin']

    wa_morning_notified = fields.Boolean(
        string='Morning Notification Sent',
        default=False,
        copy=False,
        help='True when delivery-day morning WhatsApp notification has been sent.',
    )

    def write(self, vals):
        if 'scheduled_date' in vals:
            vals = dict(vals)
            vals['wa_morning_notified'] = False
        return super().write(vals)

    def _wa_get_delivery_timezone(self):
        tz_name = self.env['ir.config_parameter'].sudo().get_param(
            'floo_whatsapp_sales.delivery_timezone', 'Asia/Jakarta',
        )
        try:
            return pytz.timezone(tz_name)
        except Exception:
            return pytz.timezone('Asia/Jakarta')

    def _wa_get_delivery_hour(self):
        hour_raw = self.env['ir.config_parameter'].sudo().get_param(
            'floo_whatsapp_sales.delivery_notify_hour', '8',
        )
        try:
            hour = int(hour_raw)
        except Exception:
            hour = 8
        return max(0, min(23, hour))

    def _cron_send_delivery_morning_notifications(self):
        tz = self._wa_get_delivery_timezone()
        target_hour = self._wa_get_delivery_hour()

        local_now = datetime.now(tz)
        if local_now.hour != target_hour or local_now.minute > 15:
            return

        today = local_now.date()
        pickings = self.search([
            ('picking_type_code', '=', 'outgoing'),
            ('scheduled_date', '!=', False),
            ('state', 'not in', ['cancel']),
            ('wa_morning_notified', '=', False),
        ])

        for picking in pickings:
            partner = picking.partner_id
            partner_phone = partner.phone_sanitized or partner.mobile or partner.phone or ''
            if not partner_phone:
                continue

            dt = fields.Datetime.from_string(picking.scheduled_date)
            if not dt:
                continue

            dt_local = pytz.UTC.localize(dt).astimezone(tz)
            if dt_local.date() != today:
                continue

            payload = {
                'event_id': str(uuid.uuid4()),
                'type': 'delivery_morning',
                'picking_id': picking.id,
                'order_id': picking.sale_id.id if picking.sale_id else False,
                'order_name': picking.sale_id.name if picking.sale_id else (picking.origin or ''),
                'partner_id': partner.id,
                'partner_name': partner.name or '',
                'partner_phone': partner_phone,
                'scheduled_date': dt_local.strftime('%d-%m-%Y %H:%M'),
            }

            sent = self._wa_post_webhook(payload)
            if sent:
                picking.wa_morning_notified = True
