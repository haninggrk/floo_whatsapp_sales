# -*- coding: utf-8 -*-
import json
import logging

import requests

from odoo import models

_logger = logging.getLogger(__name__)


class FlooWebhookMixin(models.AbstractModel):
    _name = 'floo.whatsapp.webhook.mixin'
    _description = 'Floo WhatsApp Webhook Helper'

    def _wa_webhook_url(self):
        return self.env['ir.config_parameter'].sudo().get_param('floo_whatsapp_sales.webhook_url', '')

    def _wa_post_webhook(self, payload):
        url = self._wa_webhook_url()
        if not url:
            return False

        try:
            response = requests.post(
                url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
                timeout=10,
            )
            response.raise_for_status()
            return True
        except Exception as exc:  # pragma: no cover
            _logger.warning('Failed to post Floo webhook payload=%s error=%s', payload, exc)
            return False
