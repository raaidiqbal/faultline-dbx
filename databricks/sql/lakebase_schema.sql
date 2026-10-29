-- Run in the Lakebase SQL editor. Lakebase CDF is configured separately in
-- the workspace UI and writes this table's history to lb_orders_history.

CREATE TABLE IF NOT EXISTS public.orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    amount_cents BIGINT NOT NULL CHECK (amount_cents >= 0),
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'paid', 'shipped', 'cancelled')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS orders_status_idx ON public.orders (status);
CREATE INDEX IF NOT EXISTS orders_updated_at_idx ON public.orders (updated_at);

INSERT INTO public.orders (order_id, customer_id, amount_cents, status)
VALUES
    ('order-001', 'customer-001', 2599, 'pending'),
    ('order-002', 'customer-002', 7499, 'paid'),
    ('order-003', 'customer-003', 1299, 'shipped')
ON CONFLICT (order_id) DO NOTHING;

-- Produce representative update and delete events after CDF is running:
-- UPDATE public.orders
-- SET status = 'paid', updated_at = CURRENT_TIMESTAMP
-- WHERE order_id = 'order-001';
--
-- DELETE FROM public.orders WHERE order_id = 'order-003';

