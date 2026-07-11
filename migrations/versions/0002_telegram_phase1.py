"""Telegram Phase 1 account links and viewer invites."""

from alembic import op
import sqlalchemy as sa


revision = '0002_telegram_phase1'
down_revision = '0001_madmext_data_library'
branch_labels = None
depends_on = None


def upgrade():
    # mx_users predates Alembic in this project. Keep fresh Railway databases
    # deployable while leaving an existing user table untouched.
    op.execute('''CREATE TABLE IF NOT EXISTS mx_users (
        email TEXT PRIMARY KEY, name TEXT, password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'viewer', created_at TIMESTAMP DEFAULT NOW()
    )''')
    op.create_table(
        'mx_telegram_links',
        sa.Column('telegram_chat_id', sa.BigInteger(), primary_key=True),
        sa.Column('telegram_username', sa.Text()),
        sa.Column('linked_email', sa.Text(), sa.ForeignKey('mx_users.email', onupdate='CASCADE', ondelete='CASCADE'), nullable=False),
        sa.Column('role_snapshot', sa.Text(), nullable=False, server_default='viewer'),
        sa.Column('linked_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index('mx_telegram_links_email_idx', 'mx_telegram_links', [sa.text('lower(linked_email)')])
    op.create_table(
        'mx_telegram_invites',
        sa.Column('invite_token', sa.Text(), primary_key=True),
        sa.Column('created_by', sa.Text(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False, server_default='viewer'),
        sa.Column('max_uses', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('used_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("role = 'viewer'", name='ck_telegram_invite_viewer_role'),
        sa.CheckConstraint('max_uses > 0', name='ck_telegram_invite_max_uses'),
        sa.CheckConstraint('used_count >= 0', name='ck_telegram_invite_used_count'),
    )
    op.create_index('mx_telegram_invites_expiry_idx', 'mx_telegram_invites', ['expires_at'])


def downgrade():
    op.drop_index('mx_telegram_invites_expiry_idx', table_name='mx_telegram_invites')
    op.drop_table('mx_telegram_invites')
    op.drop_index('mx_telegram_links_email_idx', table_name='mx_telegram_links')
    op.drop_table('mx_telegram_links')
