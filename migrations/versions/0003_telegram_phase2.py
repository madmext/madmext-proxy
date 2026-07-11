"""Telegram Phase 2 AI usage and distributed rate limiting."""

from alembic import op
import sqlalchemy as sa


revision = '0003_telegram_phase2'
down_revision = '0002_telegram_phase1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('mx_ai_usage',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('chat_id', sa.BigInteger()), sa.Column('actor_email', sa.Text()),
        sa.Column('tokens_in', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tokens_out', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_estimate_usd', sa.Numeric(14, 8), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('mx_ai_usage_actor_time_idx', 'mx_ai_usage', ['actor_email', 'created_at'])
    op.create_table('mx_telegram_rate_events',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('mx_telegram_rate_chat_time_idx', 'mx_telegram_rate_events', ['chat_id', 'occurred_at'])


def downgrade():
    op.drop_table('mx_telegram_rate_events')
    op.drop_table('mx_ai_usage')
