# Generated by Django 5.2.3 on 2025-06-24 19:10

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0001_initial'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='orderitem',
            new_name='store_order_order_i_ec571c_idx',
            old_name='store_order_order_i_04434a_idx',
        ),
        migrations.RenameIndex(
            model_name='orderitem',
            new_name='store_order_product_f34ce4_idx',
            old_name='store_order_product_b5e61c_idx',
        ),
        migrations.AlterModelTable(
            name='orderitem',
            table=None,
        ),
    ]
