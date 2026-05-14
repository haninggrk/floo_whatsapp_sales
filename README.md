# Floo WhatsApp Sales (Odoo Module)

Customer-only WhatsApp order backend for Odoo.

## Features

- Detect customer by WhatsApp phone number.
- Create customer automatically when number is unknown.
- Require editable free-text shipping address before checkout.
- Expose tagged product catalog only (`is_whatsapp_orderable`).
- Create quotation + payment link using Odoo portal/payment flow.
- Auto-confirm order and post invoice when payment transaction becomes `done`.
- Emit morning delivery webhook at configured local time (default 08:00 WIB).

## Configuration

After installing module:

1. Go to **Sales > Configuration > Settings**.
2. Set:
   - **WhatsApp Node Webhook URL**
   - **Delivery Notification Timezone** (default `Asia/Jakarta`)
   - **Delivery Notification Hour** (default `8`)

## JSON-RPC methods used by Node server

Model: `sale.order`

- `wa_get_customer_by_phone(phone)`
- `wa_find_or_create_customer(phone, name)`
- `wa_update_customer_address(partner_id, address)`
- `wa_list_whatsapp_products(partner_id, search, limit, offset)`
- `wa_create_order_with_payment(partner_id, phone, items)`
- `wa_process_paid_order(order_id, payment_reference='')`

## Deployment (Git-based)

This module is intended to live in your Git repository and be pulled directly into an existing Odoo addons directory.

Example inside your Odoo server:

```bash
cd /mnt/extra-addons/floo_whatsapp_sales
git pull
odoo -c /etc/odoo/odoo.conf -u floo_whatsapp_sales -d <your_db> --stop-after-init
```

Then restart Odoo service/container.
