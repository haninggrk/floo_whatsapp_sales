# -*- coding: utf-8 -*-
import uuid

from odoo import api, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = ['sale.order', 'floo.whatsapp.webhook.mixin']

    @api.model
    def _wa_normalize_phone(self, phone):
        digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
        if not digits:
            return ''
        if digits.startswith('0'):
            digits = '62' + digits[1:]
        if not digits.startswith('62'):
            digits = '62' + digits
        return '+' + digits

    @api.model
    def _wa_phone_candidates(self, phone):
        normalized = self._wa_normalize_phone(phone)
        if not normalized:
            return []
        digits = normalized.replace('+', '')
        candidates = [normalized, digits]
        if digits.startswith('62') and len(digits) > 2:
            candidates.append('0' + digits[2:])
        return [c for c in candidates if c]

    @api.model
    def _wa_find_partner_by_phone(self, phone):
        partner_model = self.env['res.partner'].sudo()
        for candidate in self._wa_phone_candidates(phone):
            partner = partner_model.search(
                ['|', ('phone', 'ilike', candidate), ('mobile', 'ilike', candidate)],
                limit=1,
            )
            if partner:
                return partner

        normalized = self._wa_normalize_phone(phone)
        if normalized and 'phone_sanitized' in partner_model._fields:
            partner = partner_model.search([('phone_sanitized', '=', normalized)], limit=1)
            if partner:
                return partner

        return partner_model.browse()

    @api.model
    def wa_get_customer_by_phone(self, phone):
        partner = self._wa_find_partner_by_phone(phone)
        if not partner:
            return {
                'found': False,
                'partner_id': None,
                'name': '',
                'wa_shipping_address': '',
            }

        return {
            'found': True,
            'partner_id': partner.id,
            'name': partner.name or '',
            'wa_shipping_address': partner.wa_shipping_address or '',
        }

    @api.model
    def wa_find_or_create_customer(self, phone, name):
        partner = self._wa_find_partner_by_phone(phone)
        if not partner:
            normalized = self._wa_normalize_phone(phone)
            partner = self.env['res.partner'].sudo().create({
                'name': name,
                'mobile': normalized or phone,
                'phone': normalized or phone,
                'customer_rank': 1,
            })

        return {
            'found': True,
            'partner_id': partner.id,
            'name': partner.name or '',
            'wa_shipping_address': partner.wa_shipping_address or '',
        }

    @api.model
    def wa_update_customer_address(self, partner_id, address):
        partner = self.env['res.partner'].sudo().browse(int(partner_id)).exists()
        if not partner:
            raise UserError('Customer tidak ditemukan.')

        if not address or len(address.strip()) < 10:
            raise UserError('Alamat terlalu singkat.')

        partner.write({
            'wa_shipping_address': address.strip(),
            'street': address.strip(),
        })

        return {'ok': True}

    @api.model
    def _wa_price_for_partner(self, product, partner):
        pricelist = partner.property_product_pricelist
        if not pricelist:
            return product.lst_price

        if hasattr(pricelist, '_get_product_price'):
            return pricelist._get_product_price(product, 1.0, partner) or product.lst_price

        if hasattr(pricelist, '_get_product_price_rule'):
            price, _rule_id = pricelist._get_product_price_rule(product, 1.0, partner)
            return price or product.lst_price

        return product.lst_price

    @api.model
    def wa_list_whatsapp_products(self, partner_id, search='', limit=10, offset=0):
        partner = self.env['res.partner'].sudo().browse(int(partner_id)).exists()
        if not partner:
            raise UserError('Customer tidak ditemukan.')

        product_model = self.env['product.product'].sudo()
        domain = [
            ('active', '=', True),
            ('sale_ok', '=', True),
            ('product_tmpl_id.is_whatsapp_orderable', '=', True),
        ]
        if search:
            domain += ['|', ('name', 'ilike', search), ('default_code', 'ilike', search)]

        total = product_model.search_count(domain)
        products = product_model.search(domain, limit=int(limit), offset=int(offset), order='name asc')

        return {
            'products': [
                {
                    'id': product.id,
                    'name': product.display_name,
                    'price': float(self._wa_price_for_partner(product, partner)),
                }
                for product in products
            ],
            'total': total,
        }

    @api.model
    def wa_create_order_with_payment(self, partner_id, phone, items):
        partner = self.env['res.partner'].sudo().browse(int(partner_id)).exists()
        if not partner:
            raise UserError('Customer tidak ditemukan.')

        if not partner.wa_shipping_address:
            raise UserError('Alamat pengiriman wajib diisi sebelum checkout.')

        if not items:
            raise UserError('Keranjang kosong.')

        order_line_commands = []
        product_model = self.env['product.product'].sudo()
        for row in items:
            product_id = int(row.get('product_id', 0))
            quantity = float(row.get('quantity', 0))
            if product_id <= 0 or quantity <= 0:
                continue

            product = product_model.browse(product_id).exists()
            if not product or not product.product_tmpl_id.is_whatsapp_orderable:
                continue

            order_line_commands.append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': quantity,
                'price_unit': self._wa_price_for_partner(product, partner),
                'name': product.display_name,
            }))

        if not order_line_commands:
            raise UserError('Tidak ada produk valid untuk diproses.')

        order = self.sudo().create({
            'partner_id': partner.id,
            'partner_invoice_id': partner.id,
            'partner_shipping_id': partner.id,
            'order_line': order_line_commands,
        })

        access_token = ''
        if hasattr(order, '_portal_ensure_token'):
            access_token = order._portal_ensure_token()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        payment_url = '/my/orders/%s' % order.id
        if access_token:
            payment_url = '%s?access_token=%s' % (payment_url, access_token)
        if base_url:
            payment_url = '%s%s' % (base_url.rstrip('/'), payment_url)

        return {
            'order_id': order.id,
            'order_name': order.name,
            'amount_total': float(order.amount_total),
            'currency': order.currency_id.name or 'IDR',
            'payment_url': payment_url,
            'partner_phone': self._wa_normalize_phone(phone) or (partner.mobile or partner.phone or ''),
        }

    @api.model
    def wa_process_paid_order(self, order_id, payment_reference=''):
        order = self.sudo().browse(int(order_id)).exists()
        if not order:
            return {'ok': False, 'reason': 'order_not_found'}

        if order.state in ('draft', 'sent'):
            order.action_confirm()

        posted_invoice = order.invoice_ids.filtered(lambda m: m.move_type == 'out_invoice' and m.state == 'posted')[:1]
        if not posted_invoice:
            invoice = order._create_invoices()
            if invoice and invoice.state == 'draft':
                invoice.action_post()
            posted_invoice = invoice[:1]

        invoice_name = posted_invoice.name if posted_invoice else ''
        invoice_url = ''
        invoice_pdf_url = ''

        if posted_invoice:
            token = ''
            if hasattr(posted_invoice, '_portal_ensure_token'):
                token = posted_invoice._portal_ensure_token()

            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
            if base_url:
                if token:
                    invoice_url = '%s/my/invoices/%s?access_token=%s' % (base_url.rstrip('/'), posted_invoice.id, token)
                    invoice_pdf_url = '%s/my/invoices/%s/download?access_token=%s' % (base_url.rstrip('/'), posted_invoice.id, token)
                else:
                    invoice_url = '%s/my/invoices/%s' % (base_url.rstrip('/'), posted_invoice.id)

        partner = order.partner_id
        partner_phone = partner.phone_sanitized or partner.mobile or partner.phone or ''

        payload = {
            'event_id': str(uuid.uuid4()),
            'type': 'payment_paid',
            'payment_reference': payment_reference or '',
            'order_id': order.id,
            'order_name': order.name,
            'partner_id': partner.id,
            'partner_name': partner.name or '',
            'partner_phone': partner_phone,
            'amount_total': float(order.amount_total),
            'currency': order.currency_id.name or 'IDR',
            'invoice_id': posted_invoice.id if posted_invoice else False,
            'invoice_name': invoice_name,
            'invoice_url': invoice_url,
            'invoice_pdf_url': invoice_pdf_url,
        }

        self._wa_post_webhook(payload)
        return {'ok': True, 'payload': payload}
