"""Madmext merkezi veri kütüphanesi başlangıç şeması."""
from alembic import op
import sqlalchemy as sa

revision = '0001_madmext_data_library'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('mx_sources',
        sa.Column('id',sa.BigInteger(),primary_key=True),sa.Column('source_key',sa.String(80),nullable=False,unique=True),
        sa.Column('name',sa.String(160),nullable=False),sa.Column('source_type',sa.String(30),nullable=False),
        sa.Column('is_active',sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column('schema_version',sa.String(30),nullable=False,server_default='1'),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_table('mx_products',
        sa.Column('id',sa.BigInteger(),primary_key=True),sa.Column('canonical_code',sa.String(120),nullable=False,unique=True),
        sa.Column('name',sa.String(500),nullable=False),sa.Column('brand',sa.String(160)),sa.Column('category',sa.String(300)),
        sa.Column('status',sa.String(30),nullable=False,server_default='active'),sa.Column('attributes',sa.JSON(),nullable=False,server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_table('mx_product_variants',
        sa.Column('id',sa.BigInteger(),primary_key=True),sa.Column('product_id',sa.BigInteger(),sa.ForeignKey('mx_products.id',ondelete='CASCADE'),nullable=False),
        sa.Column('sku',sa.String(160),nullable=False,unique=True),sa.Column('barcode',sa.String(160)),sa.Column('model_code',sa.String(160)),
        sa.Column('color',sa.String(120)),sa.Column('size',sa.String(80)),sa.Column('attributes',sa.JSON(),nullable=False,server_default=sa.text("'{}'::jsonb")),
        sa.Column('is_active',sa.Boolean(),nullable=False,server_default=sa.true()))
    op.create_table('mx_inventory_snapshots',
        sa.Column('id',sa.BigInteger(),primary_key=True),sa.Column('variant_id',sa.BigInteger(),sa.ForeignKey('mx_product_variants.id'),nullable=False),
        sa.Column('source_id',sa.BigInteger(),sa.ForeignKey('mx_sources.id'),nullable=False),sa.Column('quantity',sa.Numeric(18,4),nullable=False),
        sa.Column('captured_at',sa.DateTime(timezone=True),nullable=False),sa.Column('source_cursor',sa.String(300)),
        sa.UniqueConstraint('variant_id','source_id','captured_at',name='uq_inventory_snapshot'))
    op.create_table('mx_price_history',
        sa.Column('id',sa.BigInteger(),primary_key=True),sa.Column('variant_id',sa.BigInteger(),sa.ForeignKey('mx_product_variants.id'),nullable=False),
        sa.Column('source_id',sa.BigInteger(),sa.ForeignKey('mx_sources.id'),nullable=False),sa.Column('list_price',sa.Numeric(18,4)),
        sa.Column('sale_price',sa.Numeric(18,4),nullable=False),sa.Column('currency',sa.String(3),nullable=False,server_default='TRY'),
        sa.Column('valid_from',sa.DateTime(timezone=True),nullable=False),sa.Column('valid_to',sa.DateTime(timezone=True)),
        sa.CheckConstraint('sale_price >= 0',name='ck_price_nonnegative'))
    op.create_table('mx_customers',
        sa.Column('id',sa.BigInteger(),primary_key=True),sa.Column('external_ref_hash',sa.String(128),nullable=False,unique=True),
        sa.Column('segment',sa.String(120)),sa.Column('consent_status',sa.String(30)),
        sa.Column('attributes',sa.JSON(),nullable=False,server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_table('mx_orders',
        sa.Column('id',sa.BigInteger(),primary_key=True),sa.Column('source_id',sa.BigInteger(),sa.ForeignKey('mx_sources.id'),nullable=False),
        sa.Column('external_id',sa.String(180),nullable=False),sa.Column('customer_id',sa.BigInteger(),sa.ForeignKey('mx_customers.id')),
        sa.Column('status',sa.String(50),nullable=False),sa.Column('currency',sa.String(3),nullable=False,server_default='TRY'),
        sa.Column('gross_total',sa.Numeric(18,4),nullable=False,server_default='0'),sa.Column('discount_total',sa.Numeric(18,4),nullable=False,server_default='0'),
        sa.Column('net_total',sa.Numeric(18,4),nullable=False,server_default='0'),sa.Column('ordered_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('source_id','external_id',name='uq_order_source_external'))
    op.create_table('mx_order_items',
        sa.Column('id',sa.BigInteger(),primary_key=True),sa.Column('order_id',sa.BigInteger(),sa.ForeignKey('mx_orders.id',ondelete='CASCADE'),nullable=False),
        sa.Column('variant_id',sa.BigInteger(),sa.ForeignKey('mx_product_variants.id')),sa.Column('quantity',sa.Numeric(18,4),nullable=False),
        sa.Column('unit_price',sa.Numeric(18,4),nullable=False),sa.Column('discount',sa.Numeric(18,4),nullable=False,server_default='0'),
        sa.Column('net_total',sa.Numeric(18,4),nullable=False))
    op.create_table('mx_returns',
        sa.Column('id',sa.BigInteger(),primary_key=True),sa.Column('order_item_id',sa.BigInteger(),sa.ForeignKey('mx_order_items.id'),nullable=False),
        sa.Column('external_id',sa.String(180)),sa.Column('status',sa.String(50),nullable=False),sa.Column('quantity',sa.Numeric(18,4),nullable=False),
        sa.Column('refund_amount',sa.Numeric(18,4),nullable=False,server_default='0'),sa.Column('reason',sa.String(500)),
        sa.Column('requested_at',sa.DateTime(timezone=True)),sa.Column('completed_at',sa.DateTime(timezone=True)))
    op.create_table('mx_business_campaigns',
        sa.Column('id',sa.BigInteger(),primary_key=True),sa.Column('name',sa.String(300),nullable=False),sa.Column('campaign_type',sa.String(80)),
        sa.Column('status',sa.String(40),nullable=False,server_default='draft'),sa.Column('starts_at',sa.DateTime(timezone=True)),
        sa.Column('ends_at',sa.DateTime(timezone=True)),sa.Column('goal',sa.String(160)),sa.Column('created_by',sa.String(320)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_table('mx_campaign_products',
        sa.Column('campaign_id',sa.BigInteger(),sa.ForeignKey('mx_business_campaigns.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('product_id',sa.BigInteger(),sa.ForeignKey('mx_products.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('campaign_price',sa.Numeric(18,4)),sa.Column('notes',sa.Text()))
    op.create_table('mx_ad_entities',
        sa.Column('id',sa.BigInteger(),primary_key=True),sa.Column('source_id',sa.BigInteger(),sa.ForeignKey('mx_sources.id'),nullable=False),
        sa.Column('entity_type',sa.String(30),nullable=False),sa.Column('external_id',sa.String(180),nullable=False),
        sa.Column('parent_id',sa.BigInteger(),sa.ForeignKey('mx_ad_entities.id')),sa.Column('name',sa.String(500),nullable=False),
        sa.Column('status',sa.String(40)),sa.Column('currency',sa.String(3),server_default='TRY'),
        sa.UniqueConstraint('source_id','entity_type','external_id',name='uq_ad_entity_source_type_external'))
    op.create_table('mx_ad_product_links',
        sa.Column('ad_entity_id',sa.BigInteger(),sa.ForeignKey('mx_ad_entities.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('product_id',sa.BigInteger(),sa.ForeignKey('mx_products.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('confidence',sa.Numeric(6,5)),sa.Column('link_method',sa.String(50)),sa.Column('confirmed_by',sa.String(320)))
    op.create_index('ix_orders_ordered_at','mx_orders',['ordered_at'])
    op.create_index('ix_inventory_variant_time','mx_inventory_snapshots',['variant_id','captured_at'])


def downgrade():
    for table in ('mx_ad_product_links','mx_ad_entities','mx_campaign_products','mx_business_campaigns','mx_returns','mx_order_items','mx_orders','mx_customers','mx_price_history','mx_inventory_snapshots','mx_product_variants','mx_products','mx_sources'):
        op.drop_table(table)
