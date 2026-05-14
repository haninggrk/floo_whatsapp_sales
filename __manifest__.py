# -*- coding: utf-8 -*-
{
    'name': 'Floo WhatsApp Sales',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Customer-only WhatsApp sales flow with payment link and morning delivery notification',
    'description': """
        Floo WhatsApp Sales
        - Customer lookup by WhatsApp phone
        - New customer onboarding via WhatsApp
        - Tagged product ordering only
        - Required editable free-text shipping address
        - Odoo payment link flow
        - Auto order confirmation and invoice posting after payment done
        - Delivery-day morning WhatsApp notification webhook
    """,
    'author': 'Floo',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'stock', 'account', 'portal', 'payment'],
    'data': [
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
        'views/product_template_views.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
