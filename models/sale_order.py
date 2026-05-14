# -*- coding: utf-8 -*-
import uuid

from odoo import api, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = ['sale.order', 'floo.whatsapp.webhook.mixin']

    @api.model
    def _wa_partner_phone_fields(self, partner_model):
        fields = []
        for field_name in ('phone_sanitized', 'mobile', 'phone'):
            if field_name in partner_model._fields:
                fields.append(field_name)
        return fields

    @api.model
    def _wa_get_partner_phone(self, partner):
        for field_name in self._wa_partner_phone_fields(partner):
            value = partner[field_name]
            if value:
                return value
        return ''

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
        phone_fields = self._wa_partner_phone_fields(partner_model)

        for candidate in self._wa_phone_candidates(phone):
            for field_name in phone_fields:
                operator = '=' if field_name == 'phone_sanitized' else 'ilike'
                partner = partner_model.search([(field_name, operator, candidate)], limit=1)
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
            create_vals = {
                'name': name,
                'customer_rank': 1,
            }
            partner_model = self.env['res.partner'].sudo()
            if 'mobile' in partner_model._fields:
                create_vals['mobile'] = normalized or phone
            if 'phone' in partner_model._fields:
                create_vals['phone'] = normalized or phone
            partner = partner_model.create(create_vals)

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
    def _wa_format_address_summary(self, partner):
        parts = [
            partner.street or '',
            partner.street2 or '',
            partner.city or '',
            partner.state_id.name if partner.state_id else '',
            partner.zip or '',
        ]
        parts = [p for p in parts if p]
        return ', '.join(parts)

    @api.model
    def wa_list_customer_addresses(self, partner_id):
        partner = self.env['res.partner'].sudo().browse(int(partner_id)).exists()
        if not partner:
            raise UserError('Customer tidak ditemukan.')

        addresses = []

        if partner.wa_shipping_address:
            addresses.append({
                'id': partner.id,
                'label': 'Alamat Utama',
                'full_address': partner.wa_shipping_address,
            })

        for child in partner.child_ids.filtered(lambda c: c.type == 'delivery'):
            addresses.append({
                'id': child.id,
                'label': child.name or 'Alamat Pengiriman',
                'full_address': self._wa_format_address_summary(child),
            })

        return {'addresses': addresses}

    @api.model
    def wa_create_customer_address(self, partner_id, payload):
        partner = self.env['res.partner'].sudo().browse(int(partner_id)).exists()
        if not partner:
            raise UserError('Customer tidak ditemukan.')

        required = ['recipient_name', 'phone', 'street', 'village', 'district', 'city', 'province', 'postal_code']
        for key in required:
            if not (payload.get(key) or '').strip():
                raise UserError('Field alamat belum lengkap: %s' % key)

        province_name = (payload.get('province') or '').strip()
        state = self.env['res.country.state'].sudo().search([('name', 'ilike', province_name)], limit=1)
        country = self.env['res.country'].sudo().search([('code', '=', 'ID')], limit=1)

        vals = {
            'parent_id': partner.id,
            'type': 'delivery',
            'name': payload.get('recipient_name').strip(),
            'street': payload.get('street').strip(),
            'street2': 'Kel. %s, Kec. %s' % (payload.get('village').strip(), payload.get('district').strip()),
            'city': payload.get('city').strip(),
            'zip': payload.get('postal_code').strip(),
            'country_id': country.id if country else False,
            'state_id': state.id if state else False,
        }

        partner_model = self.env['res.partner'].sudo()
        if 'mobile' in partner_model._fields:
            vals['mobile'] = payload.get('phone').strip()
        if 'phone' in partner_model._fields:
            vals['phone'] = payload.get('phone').strip()

        address = partner_model.create(vals)
        return {
            'address_id': address.id,
            'label': address.name,
            'full_address': self._wa_format_address_summary(address),
        }

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
    def wa_create_order_with_payment(self, partner_id, phone, items, shipping_address_id=False):
        partner = self.env['res.partner'].sudo().browse(int(partner_id)).exists()
        if not partner:
            raise UserError('Customer tidak ditemukan.')

        if not partner.wa_shipping_address:
            raise UserError('Alamat pengiriman wajib diisi sebelum checkout.')

        if not items:
            raise UserError('Keranjang kosong.')

        shipping_partner_id = partner.id
        if shipping_address_id:
            shipping_partner = self.env['res.partner'].sudo().browse(int(shipping_address_id)).exists()
            if shipping_partner and (shipping_partner.id == partner.id or shipping_partner.parent_id.id == partner.id):
                shipping_partner_id = shipping_partner.id

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

        order_vals = {
            'partner_id': partner.id,
            'partner_invoice_id': partner.id,
            'partner_shipping_id': shipping_partner_id,
            'order_line': order_line_commands,
        }

        if 'require_signature' in self._fields:
            order_vals['require_signature'] = False
        if 'require_payment' in self._fields:
            order_vals['require_payment'] = True

        order = self.sudo().create(order_vals)

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
            'partner_phone': self._wa_normalize_phone(phone) or self._wa_get_partner_phone(partner),
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
        partner_phone = self._wa_get_partner_phone(partner)

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
