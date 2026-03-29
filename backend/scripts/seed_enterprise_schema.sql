-- =============================================================================
-- Contoso Retail Operations — Enterprise Sample Schema for Azure SQL
-- =============================================================================
-- Schemas: hr, sales, inventory, finance, support
-- Idempotent: safe to re-run (drops and recreates objects)
-- =============================================================================

-- ============================================
-- 0. DROP EXISTING OBJECTS (reverse dependency order)
-- ============================================

-- Views
IF OBJECT_ID('support.v_ticket_resolution_stats', 'V') IS NOT NULL DROP VIEW support.v_ticket_resolution_stats;
GO
IF OBJECT_ID('inventory.v_low_stock_alerts', 'V') IS NOT NULL DROP VIEW inventory.v_low_stock_alerts;
GO
IF OBJECT_ID('hr.v_department_headcount', 'V') IS NOT NULL DROP VIEW hr.v_department_headcount;
GO
IF OBJECT_ID('sales.v_monthly_revenue', 'V') IS NOT NULL DROP VIEW sales.v_monthly_revenue;
GO
IF OBJECT_ID('sales.v_order_summary', 'V') IS NOT NULL DROP VIEW sales.v_order_summary;
GO

-- Tables (children first)
IF OBJECT_ID('support.ticket_comments', 'U') IS NOT NULL DROP TABLE support.ticket_comments;
GO
IF OBJECT_ID('support.tickets', 'U') IS NOT NULL DROP TABLE support.tickets;
GO
IF OBJECT_ID('finance.payments', 'U') IS NOT NULL DROP TABLE finance.payments;
GO
IF OBJECT_ID('finance.invoices', 'U') IS NOT NULL DROP TABLE finance.invoices;
GO
IF OBJECT_ID('finance.budget_allocations', 'U') IS NOT NULL DROP TABLE finance.budget_allocations;
GO
IF OBJECT_ID('inventory.stock_levels', 'U') IS NOT NULL DROP TABLE inventory.stock_levels;
GO
IF OBJECT_ID('inventory.product_suppliers', 'U') IS NOT NULL DROP TABLE inventory.product_suppliers;
GO
IF OBJECT_ID('inventory.warehouses', 'U') IS NOT NULL DROP TABLE inventory.warehouses;
GO
IF OBJECT_ID('inventory.suppliers', 'U') IS NOT NULL DROP TABLE inventory.suppliers;
GO
IF OBJECT_ID('sales.order_promotions', 'U') IS NOT NULL DROP TABLE sales.order_promotions;
GO
IF OBJECT_ID('sales.promotions', 'U') IS NOT NULL DROP TABLE sales.promotions;
GO
IF OBJECT_ID('sales.order_items', 'U') IS NOT NULL DROP TABLE sales.order_items;
GO
IF OBJECT_ID('sales.orders', 'U') IS NOT NULL DROP TABLE sales.orders;
GO
IF OBJECT_ID('inventory.products', 'U') IS NOT NULL DROP TABLE inventory.products;
GO
IF OBJECT_ID('inventory.categories', 'U') IS NOT NULL DROP TABLE inventory.categories;
GO
IF OBJECT_ID('sales.customers', 'U') IS NOT NULL DROP TABLE sales.customers;
GO
IF OBJECT_ID('sales.territories', 'U') IS NOT NULL DROP TABLE sales.territories;
GO
IF OBJECT_ID('sales.regions', 'U') IS NOT NULL DROP TABLE sales.regions;
GO
IF OBJECT_ID('hr.salary_history', 'U') IS NOT NULL DROP TABLE hr.salary_history;
GO
IF OBJECT_ID('hr.employee_addresses', 'U') IS NOT NULL DROP TABLE hr.employee_addresses;
GO
IF OBJECT_ID('hr.employees', 'U') IS NOT NULL DROP TABLE hr.employees;
GO
IF OBJECT_ID('hr.departments', 'U') IS NOT NULL DROP TABLE hr.departments;
GO

-- ============================================
-- 1. CREATE SCHEMAS
-- ============================================

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'hr')
    EXEC('CREATE SCHEMA hr');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'sales')
    EXEC('CREATE SCHEMA sales');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'inventory')
    EXEC('CREATE SCHEMA inventory');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'finance')
    EXEC('CREATE SCHEMA finance');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'support')
    EXEC('CREATE SCHEMA support');
GO

-- ============================================
-- 2. HR SCHEMA
-- ============================================

CREATE TABLE hr.departments (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    name            NVARCHAR(100)   NOT NULL UNIQUE,
    budget          DECIMAL(15,2)   NOT NULL DEFAULT 0,
    manager_employee_id INT        NULL,  -- FK added after employees table
    parent_department_id INT       NULL REFERENCES hr.departments(id),
    created_at      DATETIME2       NOT NULL DEFAULT GETUTCDATE()
);
GO

CREATE TABLE hr.employees (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    first_name      NVARCHAR(50)    NOT NULL,
    last_name       NVARCHAR(50)    NOT NULL,
    email           NVARCHAR(150)   NOT NULL UNIQUE,
    phone           NVARCHAR(20)    NULL,
    hire_date       DATE            NOT NULL,
    termination_date DATE           NULL,
    salary          DECIMAL(12,2)   NOT NULL CHECK (salary >= 0),
    department_id   INT             NOT NULL REFERENCES hr.departments(id),
    manager_id      INT             NULL REFERENCES hr.employees(id),
    job_title       NVARCHAR(100)   NOT NULL,
    is_active       BIT             NOT NULL DEFAULT 1,
    created_at      DATETIME2       NOT NULL DEFAULT GETUTCDATE()
);
GO

-- Now add FK from departments.manager_employee_id -> employees.id
ALTER TABLE hr.departments
    ADD CONSTRAINT FK_departments_manager
    FOREIGN KEY (manager_employee_id) REFERENCES hr.employees(id);
GO

CREATE INDEX IX_employees_department ON hr.employees(department_id);
GO
CREATE INDEX IX_employees_manager ON hr.employees(manager_id);
GO
CREATE INDEX IX_employees_hire_date ON hr.employees(hire_date);
GO

CREATE TABLE hr.employee_addresses (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    employee_id     INT             NOT NULL REFERENCES hr.employees(id) ON DELETE CASCADE,
    address_type    NVARCHAR(20)    NOT NULL CHECK (address_type IN ('home', 'mailing')),
    street_address  NVARCHAR(200)   NOT NULL,
    city            NVARCHAR(100)   NOT NULL,
    state           NVARCHAR(50)    NULL,
    postal_code     NVARCHAR(20)    NOT NULL,
    country         NVARCHAR(50)    NOT NULL DEFAULT 'US'
);
GO

CREATE TABLE hr.salary_history (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    employee_id     INT             NOT NULL REFERENCES hr.employees(id) ON DELETE CASCADE,
    effective_date  DATE            NOT NULL,
    old_salary      DECIMAL(12,2)   NOT NULL,
    new_salary      DECIMAL(12,2)   NOT NULL,
    change_reason   NVARCHAR(50)    NOT NULL CHECK (change_reason IN ('hire', 'promotion', 'annual_review', 'market_adjustment', 'role_change'))
);
GO

CREATE INDEX IX_salary_history_employee ON hr.salary_history(employee_id, effective_date);
GO

-- ============================================
-- 3. SALES SCHEMA
-- ============================================

CREATE TABLE sales.regions (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    name            NVARCHAR(50)    NOT NULL UNIQUE,
    country         NVARCHAR(50)    NOT NULL DEFAULT 'US'
);
GO

CREATE TABLE sales.territories (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    name            NVARCHAR(100)   NOT NULL,
    region_id       INT             NOT NULL REFERENCES sales.regions(id)
);
GO

CREATE TABLE sales.customers (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    first_name      NVARCHAR(50)    NOT NULL,
    last_name       NVARCHAR(50)    NOT NULL,
    email           NVARCHAR(150)   NOT NULL UNIQUE,
    phone           NVARCHAR(20)    NULL,
    company_name    NVARCHAR(150)   NULL,
    territory_id    INT             NULL REFERENCES sales.territories(id),
    customer_type   NVARCHAR(10)    NOT NULL CHECK (customer_type IN ('B2B', 'B2C')) DEFAULT 'B2C',
    credit_limit    DECIMAL(12,2)   NULL,
    created_at      DATETIME2       NOT NULL DEFAULT GETUTCDATE()
);
GO

CREATE INDEX IX_customers_territory ON sales.customers(territory_id);
GO
CREATE INDEX IX_customers_type ON sales.customers(customer_type);
GO

CREATE TABLE sales.orders (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    customer_id     INT             NOT NULL REFERENCES sales.customers(id),
    employee_id     INT             NULL REFERENCES hr.employees(id),
    order_date      DATE            NOT NULL,
    required_date   DATE            NULL,
    shipped_date    DATE            NULL,
    status          NVARCHAR(20)    NOT NULL CHECK (status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled', 'returned')) DEFAULT 'pending',
    shipping_cost   DECIMAL(10,2)   NOT NULL DEFAULT 0,
    notes           NVARCHAR(500)   NULL,
    created_at      DATETIME2       NOT NULL DEFAULT GETUTCDATE()
);
GO

CREATE INDEX IX_orders_customer ON sales.orders(customer_id);
GO
CREATE INDEX IX_orders_employee ON sales.orders(employee_id);
GO
CREATE INDEX IX_orders_date ON sales.orders(order_date);
GO
CREATE INDEX IX_orders_status ON sales.orders(status);
GO

-- ============================================
-- 4. INVENTORY SCHEMA (products needed before order_items)
-- ============================================

CREATE TABLE inventory.categories (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    name            NVARCHAR(100)   NOT NULL,
    description     NVARCHAR(500)   NULL,
    parent_category_id INT          NULL REFERENCES inventory.categories(id)
);
GO

CREATE TABLE inventory.products (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    name            NVARCHAR(200)   NOT NULL,
    sku             NVARCHAR(50)    NOT NULL UNIQUE,
    category_id     INT             NOT NULL REFERENCES inventory.categories(id),
    unit_price      DECIMAL(10,2)   NOT NULL CHECK (unit_price >= 0),
    cost_price      DECIMAL(10,2)   NOT NULL CHECK (cost_price >= 0),
    weight_kg       DECIMAL(8,3)    NULL,
    is_discontinued BIT             NOT NULL DEFAULT 0,
    created_at      DATETIME2       NOT NULL DEFAULT GETUTCDATE()
);
GO

CREATE INDEX IX_products_category ON inventory.products(category_id);
GO
CREATE INDEX IX_products_sku ON inventory.products(sku);
GO

-- Now create order_items (depends on orders + products)
CREATE TABLE sales.order_items (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    order_id        INT             NOT NULL REFERENCES sales.orders(id) ON DELETE CASCADE,
    product_id      INT             NOT NULL REFERENCES inventory.products(id),
    quantity        INT             NOT NULL CHECK (quantity > 0),
    unit_price      DECIMAL(10,2)   NOT NULL CHECK (unit_price >= 0),
    discount_percent DECIMAL(5,2)   NOT NULL DEFAULT 0 CHECK (discount_percent >= 0 AND discount_percent <= 100)
);
GO

CREATE INDEX IX_order_items_order ON sales.order_items(order_id);
GO
CREATE INDEX IX_order_items_product ON sales.order_items(product_id);
GO

CREATE TABLE sales.promotions (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    name            NVARCHAR(100)   NOT NULL,
    discount_percent DECIMAL(5,2)   NOT NULL CHECK (discount_percent > 0 AND discount_percent <= 100),
    start_date      DATE            NOT NULL,
    end_date        DATE            NOT NULL,
    min_order_amount DECIMAL(10,2)  NULL,
    is_active       BIT             NOT NULL DEFAULT 1,
    CONSTRAINT CK_promo_dates CHECK (end_date >= start_date)
);
GO

CREATE TABLE sales.order_promotions (
    order_id        INT             NOT NULL REFERENCES sales.orders(id) ON DELETE CASCADE,
    promotion_id    INT             NOT NULL REFERENCES sales.promotions(id),
    PRIMARY KEY (order_id, promotion_id)
);
GO

-- Remaining inventory tables
CREATE TABLE inventory.suppliers (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    company_name    NVARCHAR(150)   NOT NULL,
    contact_name    NVARCHAR(100)   NULL,
    email           NVARCHAR(150)   NULL,
    phone           NVARCHAR(20)    NULL,
    country         NVARCHAR(50)    NOT NULL,
    reliability_rating TINYINT      NULL CHECK (reliability_rating BETWEEN 1 AND 5)
);
GO

CREATE TABLE inventory.product_suppliers (
    product_id      INT             NOT NULL REFERENCES inventory.products(id),
    supplier_id     INT             NOT NULL REFERENCES inventory.suppliers(id),
    lead_time_days  INT             NOT NULL CHECK (lead_time_days > 0),
    supply_cost     DECIMAL(10,2)   NOT NULL CHECK (supply_cost >= 0),
    PRIMARY KEY (product_id, supplier_id)
);
GO

CREATE TABLE inventory.warehouses (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    name            NVARCHAR(100)   NOT NULL,
    city            NVARCHAR(100)   NOT NULL,
    state           NVARCHAR(50)    NULL,
    country         NVARCHAR(50)    NOT NULL DEFAULT 'US',
    capacity_units  INT             NOT NULL CHECK (capacity_units > 0)
);
GO

CREATE TABLE inventory.stock_levels (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    product_id      INT             NOT NULL REFERENCES inventory.products(id),
    warehouse_id    INT             NOT NULL REFERENCES inventory.warehouses(id),
    quantity_on_hand INT            NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    reorder_point   INT             NOT NULL DEFAULT 10,
    last_restocked_at DATETIME2     NULL,
    CONSTRAINT UQ_stock_product_warehouse UNIQUE (product_id, warehouse_id)
);
GO

-- ============================================
-- 5. FINANCE SCHEMA
-- ============================================

CREATE TABLE finance.invoices (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    order_id        INT             NOT NULL REFERENCES sales.orders(id),
    invoice_date    DATE            NOT NULL,
    due_date        DATE            NOT NULL,
    total_amount    DECIMAL(12,2)   NOT NULL CHECK (total_amount >= 0),
    tax_amount      DECIMAL(10,2)   NOT NULL DEFAULT 0,
    status          NVARCHAR(20)    NOT NULL CHECK (status IN ('draft', 'sent', 'paid', 'overdue', 'void')) DEFAULT 'draft',
    paid_date       DATE            NULL
);
GO

CREATE INDEX IX_invoices_order ON finance.invoices(order_id);
GO
CREATE INDEX IX_invoices_status ON finance.invoices(status);
GO
CREATE INDEX IX_invoices_due_date ON finance.invoices(due_date);
GO

CREATE TABLE finance.payments (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    invoice_id      INT             NOT NULL REFERENCES finance.invoices(id),
    payment_date    DATE            NOT NULL,
    amount          DECIMAL(12,2)   NOT NULL CHECK (amount > 0),
    payment_method  NVARCHAR(30)    NOT NULL CHECK (payment_method IN ('credit_card', 'bank_transfer', 'check', 'cash', 'wire', 'paypal')),
    reference_number NVARCHAR(50)   NULL
);
GO

CREATE INDEX IX_payments_invoice ON finance.payments(invoice_id);
GO

CREATE TABLE finance.budget_allocations (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    department_id   INT             NOT NULL REFERENCES hr.departments(id),
    fiscal_year     INT             NOT NULL,
    fiscal_quarter  TINYINT         NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4),
    allocated_amount DECIMAL(15,2)  NOT NULL CHECK (allocated_amount >= 0),
    spent_amount    DECIMAL(15,2)   NOT NULL DEFAULT 0 CHECK (spent_amount >= 0),
    category        NVARCHAR(50)    NOT NULL CHECK (category IN ('personnel', 'operations', 'marketing', 'technology', 'facilities', 'travel', 'training')),
    CONSTRAINT UQ_budget_dept_year_qtr_cat UNIQUE (department_id, fiscal_year, fiscal_quarter, category)
);
GO

-- ============================================
-- 6. SUPPORT SCHEMA
-- ============================================

CREATE TABLE support.tickets (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    customer_id     INT             NOT NULL REFERENCES sales.customers(id),
    assigned_employee_id INT        NULL REFERENCES hr.employees(id),
    subject         NVARCHAR(200)   NOT NULL,
    description     NVARCHAR(2000)  NULL,
    priority        NVARCHAR(10)    NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'critical')) DEFAULT 'medium',
    status          NVARCHAR(20)    NOT NULL CHECK (status IN ('open', 'in_progress', 'waiting_customer', 'resolved', 'closed')) DEFAULT 'open',
    category        NVARCHAR(50)    NOT NULL CHECK (category IN ('billing', 'shipping', 'product_defect', 'returns', 'account', 'general')),
    created_at      DATETIME2       NOT NULL DEFAULT GETUTCDATE(),
    resolved_at     DATETIME2       NULL,
    satisfaction_rating TINYINT     NULL CHECK (satisfaction_rating BETWEEN 1 AND 5)
);
GO

CREATE INDEX IX_tickets_customer ON support.tickets(customer_id);
GO
CREATE INDEX IX_tickets_assigned ON support.tickets(assigned_employee_id);
GO
CREATE INDEX IX_tickets_status ON support.tickets(status);
GO
CREATE INDEX IX_tickets_priority ON support.tickets(priority);
GO

CREATE TABLE support.ticket_comments (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    ticket_id       INT             NOT NULL REFERENCES support.tickets(id) ON DELETE CASCADE,
    author_employee_id INT          NULL REFERENCES hr.employees(id),
    comment_text    NVARCHAR(2000)  NOT NULL,
    is_internal     BIT             NOT NULL DEFAULT 0,
    created_at      DATETIME2       NOT NULL DEFAULT GETUTCDATE()
);
GO

CREATE INDEX IX_ticket_comments_ticket ON support.ticket_comments(ticket_id);
GO

-- ============================================
-- 7. VIEWS
-- ============================================

CREATE VIEW sales.v_order_summary AS
SELECT
    o.id              AS order_id,
    o.order_date,
    o.status          AS order_status,
    c.id              AS customer_id,
    c.first_name + ' ' + c.last_name AS customer_name,
    c.company_name,
    e.first_name + ' ' + e.last_name AS sales_rep,
    COUNT(oi.id)      AS item_count,
    SUM(oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100.0)) AS order_total,
    o.shipping_cost
FROM sales.orders o
JOIN sales.customers c ON c.id = o.customer_id
LEFT JOIN hr.employees e ON e.id = o.employee_id
LEFT JOIN sales.order_items oi ON oi.order_id = o.id
GROUP BY o.id, o.order_date, o.status, c.id, c.first_name, c.last_name,
         c.company_name, e.first_name, e.last_name, o.shipping_cost;
GO

CREATE VIEW sales.v_monthly_revenue AS
SELECT
    YEAR(o.order_date)  AS order_year,
    MONTH(o.order_date) AS order_month,
    COUNT(DISTINCT o.id) AS order_count,
    SUM(oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100.0)) AS gross_revenue,
    SUM(o.shipping_cost) AS total_shipping,
    SUM(SUM(oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100.0)))
        OVER (ORDER BY YEAR(o.order_date), MONTH(o.order_date)) AS cumulative_revenue
FROM sales.orders o
JOIN sales.order_items oi ON oi.order_id = o.id
WHERE o.status NOT IN ('cancelled', 'returned')
GROUP BY YEAR(o.order_date), MONTH(o.order_date);
GO

CREATE VIEW hr.v_department_headcount AS
SELECT
    d.id              AS department_id,
    d.name            AS department_name,
    d.budget,
    COUNT(e.id)       AS headcount,
    AVG(e.salary)     AS avg_salary,
    SUM(e.salary)     AS total_salary_cost,
    CASE WHEN d.budget > 0
         THEN ROUND(SUM(e.salary) / d.budget * 100, 1)
         ELSE 0
    END               AS budget_utilization_pct
FROM hr.departments d
LEFT JOIN hr.employees e ON e.department_id = d.id AND e.is_active = 1
GROUP BY d.id, d.name, d.budget;
GO

CREATE VIEW inventory.v_low_stock_alerts AS
SELECT
    p.id              AS product_id,
    p.name            AS product_name,
    p.sku,
    w.name            AS warehouse_name,
    w.city            AS warehouse_city,
    sl.quantity_on_hand,
    sl.reorder_point,
    sl.last_restocked_at,
    s.company_name    AS primary_supplier,
    ps.lead_time_days
FROM inventory.stock_levels sl
JOIN inventory.products p ON p.id = sl.product_id
JOIN inventory.warehouses w ON w.id = sl.warehouse_id
LEFT JOIN inventory.product_suppliers ps ON ps.product_id = p.id
LEFT JOIN inventory.suppliers s ON s.id = ps.supplier_id
WHERE sl.quantity_on_hand <= sl.reorder_point
  AND p.is_discontinued = 0;
GO

CREATE VIEW support.v_ticket_resolution_stats AS
SELECT
    t.category,
    t.priority,
    COUNT(*)                                              AS ticket_count,
    SUM(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 ELSE 0 END) AS resolved_count,
    AVG(CASE WHEN t.resolved_at IS NOT NULL
             THEN DATEDIFF(HOUR, t.created_at, t.resolved_at)
             ELSE NULL END)                               AS avg_resolution_hours,
    AVG(CAST(t.satisfaction_rating AS DECIMAL(3,1)))      AS avg_satisfaction
FROM support.tickets t
GROUP BY t.category, t.priority;
GO

-- ============================================
-- 8. SEED DATA
-- ============================================

-- 8.1  HR: Departments
SET IDENTITY_INSERT hr.departments ON;
INSERT INTO hr.departments (id, name, budget, parent_department_id) VALUES
(1,  'Executive',         5000000.00, NULL),
(2,  'Engineering',       8000000.00, 1),
(3,  'Sales',             4000000.00, 1),
(4,  'Marketing',         3000000.00, 1),
(5,  'Human Resources',   1500000.00, 1),
(6,  'Finance',           2000000.00, 1),
(7,  'Customer Support',  2500000.00, 1),
(8,  'Backend Engineering',3500000.00, 2),
(9,  'Frontend Engineering',3000000.00, 2),
(10, 'Data Engineering',  2500000.00, 2),
(11, 'DevOps',            1800000.00, 2),
(12, 'Product',           2200000.00, 1);
SET IDENTITY_INSERT hr.departments OFF;
GO

-- 8.2  HR: Employees (80 employees)
SET IDENTITY_INSERT hr.employees ON;
INSERT INTO hr.employees (id, first_name, last_name, email, phone, hire_date, salary, department_id, manager_id, job_title, is_active) VALUES
-- Executive
(1,  'Sarah',   'Chen',       'sarah.chen@contoso.com',        '555-0101', '2019-01-15', 250000.00, 1,  NULL, 'CEO', 1),
(2,  'Michael', 'Torres',     'michael.torres@contoso.com',    '555-0102', '2019-03-01', 220000.00, 1,  1,    'COO', 1),
(3,  'Jessica', 'Williams',   'jessica.williams@contoso.com',  '555-0103', '2019-06-10', 210000.00, 1,  1,    'CFO', 1),
-- Engineering Leadership
(4,  'David',   'Kim',        'david.kim@contoso.com',         '555-0104', '2019-02-20', 200000.00, 2,  1,    'VP of Engineering', 1),
(5,  'Priya',   'Patel',      'priya.patel@contoso.com',       '555-0105', '2019-08-05', 185000.00, 8,  4,    'Director of Backend', 1),
(6,  'James',   'O''Brien',   'james.obrien@contoso.com',      '555-0106', '2020-01-13', 180000.00, 9,  4,    'Director of Frontend', 1),
(7,  'Lin',     'Zhang',      'lin.zhang@contoso.com',         '555-0107', '2020-03-22', 175000.00, 10, 4,    'Director of Data', 1),
-- Sales Leadership
(8,  'Maria',   'Garcia',     'maria.garcia@contoso.com',      '555-0108', '2019-04-15', 190000.00, 3,  2,    'VP of Sales', 1),
(9,  'Robert',  'Johnson',    'robert.johnson@contoso.com',    '555-0109', '2020-02-01', 160000.00, 3,  8,    'Regional Sales Director', 1),
(10, 'Emily',   'Davis',      'emily.davis@contoso.com',       '555-0110', '2020-05-18', 155000.00, 3,  8,    'Regional Sales Director', 1),
-- Marketing
(11, 'Alex',    'Rivera',     'alex.rivera@contoso.com',       '555-0111', '2019-09-01', 170000.00, 4,  2,    'VP of Marketing', 1),
(12, 'Sophie',  'Martin',     'sophie.martin@contoso.com',     '555-0112', '2021-01-10', 110000.00, 4,  11,   'Marketing Manager', 1),
-- HR
(13, 'Karen',   'Taylor',     'karen.taylor@contoso.com',      '555-0113', '2019-05-01', 150000.00, 5,  2,    'HR Director', 1),
(14, 'Daniel',  'Lee',        'daniel.lee@contoso.com',        '555-0114', '2021-03-15', 85000.00,  5,  13,   'HR Specialist', 1),
-- Finance
(15, 'Thomas',  'Anderson',   'thomas.anderson@contoso.com',   '555-0115', '2019-07-20', 160000.00, 6,  3,    'Finance Director', 1),
(16, 'Rachel',  'Clark',      'rachel.clark@contoso.com',      '555-0116', '2021-06-01', 95000.00,  6,  15,   'Senior Accountant', 1),
-- Customer Support
(17, 'Chris',   'Wilson',     'chris.wilson@contoso.com',      '555-0117', '2020-04-10', 140000.00, 7,  2,    'Support Director', 1),
(18, 'Ashley',  'Brown',      'ashley.brown@contoso.com',      '555-0118', '2021-02-14', 75000.00,  7,  17,   'Support Lead', 1),
-- Product
(19, 'Nathan',  'Wright',     'nathan.wright@contoso.com',     '555-0119', '2020-01-06', 175000.00, 12, 1,    'VP of Product', 1),
(20, 'Olivia',  'Scott',      'olivia.scott@contoso.com',      '555-0120', '2020-09-14', 140000.00, 12, 19,   'Senior Product Manager', 1),
-- Backend Engineers
(21, 'Raj',     'Gupta',      'raj.gupta@contoso.com',         '555-0121', '2020-06-01', 155000.00, 8,  5,    'Staff Engineer', 1),
(22, 'Anna',    'Kowalski',   'anna.kowalski@contoso.com',     '555-0122', '2020-08-15', 145000.00, 8,  5,    'Senior Engineer', 1),
(23, 'Marcus',  'Reed',       'marcus.reed@contoso.com',       '555-0123', '2021-01-20', 130000.00, 8,  5,    'Senior Engineer', 1),
(24, 'Yuki',    'Tanaka',     'yuki.tanaka@contoso.com',       '555-0124', '2021-04-05', 120000.00, 8,  21,   'Software Engineer', 1),
(25, 'Omar',    'Hassan',     'omar.hassan@contoso.com',       '555-0125', '2021-07-12', 115000.00, 8,  21,   'Software Engineer', 1),
(26, 'Elena',   'Volkov',     'elena.volkov@contoso.com',      '555-0126', '2022-01-10', 110000.00, 8,  22,   'Software Engineer', 1),
(27, 'Liam',    'Murphy',     'liam.murphy@contoso.com',       '555-0127', '2022-03-21', 105000.00, 8,  22,   'Junior Engineer', 1),
(28, 'Sofia',   'Rossi',      'sofia.rossi@contoso.com',       '555-0128', '2022-06-14', 100000.00, 8,  23,   'Junior Engineer', 1),
-- Frontend Engineers
(29, 'Tyler',   'Morgan',     'tyler.morgan@contoso.com',      '555-0129', '2020-07-01', 150000.00, 9,  6,    'Staff Engineer', 1),
(30, 'Mia',     'Campbell',   'mia.campbell@contoso.com',      '555-0130', '2020-11-16', 140000.00, 9,  6,    'Senior Engineer', 1),
(31, 'Ethan',   'Brooks',     'ethan.brooks@contoso.com',      '555-0131', '2021-02-08', 130000.00, 9,  29,   'Senior Engineer', 1),
(32, 'Chloe',   'Evans',      'chloe.evans@contoso.com',       '555-0132', '2021-09-20', 115000.00, 9,  29,   'Software Engineer', 1),
(33, 'Noah',    'Cooper',     'noah.cooper@contoso.com',       '555-0133', '2022-02-14', 110000.00, 9,  30,   'Software Engineer', 1),
(34, 'Isabella','Price',      'isabella.price@contoso.com',    '555-0134', '2022-08-01', 100000.00, 9,  30,   'Junior Engineer', 1),
-- Data Engineers
(35, 'Arun',    'Sharma',     'arun.sharma@contoso.com',       '555-0135', '2020-09-01', 155000.00, 10, 7,    'Staff Data Engineer', 1),
(36, 'Hannah',  'Bennett',    'hannah.bennett@contoso.com',    '555-0136', '2021-01-15', 140000.00, 10, 7,    'Senior Data Engineer', 1),
(37, 'Lucas',   'Gray',       'lucas.gray@contoso.com',        '555-0137', '2021-05-10', 130000.00, 10, 35,   'Data Engineer', 1),
(38, 'Zoe',     'Foster',     'zoe.foster@contoso.com',        '555-0138', '2022-01-20', 120000.00, 10, 35,   'Data Engineer', 1),
(39, 'Kai',     'Nakamura',   'kai.nakamura@contoso.com',      '555-0139', '2022-07-05', 110000.00, 10, 36,   'Junior Data Engineer', 1),
-- DevOps
(40, 'Sam',     'Butler',     'sam.butler@contoso.com',        '555-0140', '2020-10-01', 150000.00, 11, 4,    'DevOps Lead', 1),
(41, 'Layla',   'Ward',       'layla.ward@contoso.com',        '555-0141', '2021-03-01', 135000.00, 11, 40,   'Senior DevOps Engineer', 1),
(42, 'Ryan',    'Howard',     'ryan.howard@contoso.com',       '555-0142', '2021-08-16', 125000.00, 11, 40,   'DevOps Engineer', 1),
(43, 'Maya',    'Santos',     'maya.santos@contoso.com',       '555-0143', '2022-04-01', 115000.00, 11, 41,   'DevOps Engineer', 1),
-- Sales Reps (under regional directors)
(44, 'Jake',    'Henderson',  'jake.henderson@contoso.com',    '555-0144', '2020-03-15', 95000.00,  3,  9,    'Account Executive', 1),
(45, 'Lily',    'Cox',        'lily.cox@contoso.com',          '555-0145', '2020-06-22', 92000.00,  3,  9,    'Account Executive', 1),
(46, 'Adam',    'Simmons',    'adam.simmons@contoso.com',      '555-0146', '2020-09-10', 90000.00,  3,  9,    'Account Executive', 1),
(47, 'Grace',   'Perry',      'grace.perry@contoso.com',       '555-0147', '2021-01-04', 88000.00,  3,  10,   'Account Executive', 1),
(48, 'Ben',     'Powell',     'ben.powell@contoso.com',        '555-0148', '2021-04-19', 85000.00,  3,  10,   'Account Executive', 1),
(49, 'Ava',     'Russell',    'ava.russell@contoso.com',       '555-0149', '2021-07-26', 82000.00,  3,  10,   'Account Executive', 1),
(50, 'Ian',     'Griffin',    'ian.griffin@contoso.com',        '555-0150', '2022-01-03', 78000.00,  3,  9,    'Sales Development Rep', 1),
(51, 'Ella',    'Hayes',      'ella.hayes@contoso.com',        '555-0151', '2022-05-16', 76000.00,  3,  10,   'Sales Development Rep', 1),
-- Marketing team
(52, 'Jack',    'Sullivan',   'jack.sullivan@contoso.com',     '555-0152', '2021-06-01', 95000.00,  4,  12,   'Content Marketing Lead', 1),
(53, 'Nora',    'Kelly',      'nora.kelly@contoso.com',        '555-0153', '2021-09-15', 85000.00,  4,  12,   'Digital Marketing Specialist', 1),
(54, 'Luke',    'Barnes',     'luke.barnes@contoso.com',       '555-0154', '2022-02-01', 80000.00,  4,  52,   'Content Writer', 1),
(55, 'Abby',    'Fisher',     'abby.fisher@contoso.com',       '555-0155', '2022-07-11', 75000.00,  4,  53,   'Social Media Coordinator', 1),
-- Support team
(56, 'Max',     'Dixon',      'max.dixon@contoso.com',         '555-0156', '2021-01-18', 68000.00,  7,  18,   'Support Agent', 1),
(57, 'Ruby',    'Palmer',     'ruby.palmer@contoso.com',       '555-0157', '2021-04-05', 66000.00,  7,  18,   'Support Agent', 1),
(58, 'Leo',     'Murray',     'leo.murray@contoso.com',        '555-0158', '2021-08-23', 65000.00,  7,  18,   'Support Agent', 1),
(59, 'Ivy',     'Stone',      'ivy.stone@contoso.com',         '555-0159', '2022-01-10', 63000.00,  7,  18,   'Support Agent', 1),
(60, 'Cole',    'Webb',       'cole.webb@contoso.com',         '555-0160', '2022-06-01', 62000.00,  7,  18,   'Support Agent', 1),
-- Additional Finance
(61, 'Tara',    'Hart',       'tara.hart@contoso.com',         '555-0161', '2021-09-01', 88000.00,  6,  15,   'Financial Analyst', 1),
(62, 'Dylan',   'Grant',      'dylan.grant@contoso.com',       '555-0162', '2022-03-14', 82000.00,  6,  16,   'Accountant', 1),
-- Additional HR
(63, 'Vera',    'Cross',      'vera.cross@contoso.com',        '555-0163', '2022-01-24', 78000.00,  5,  13,   'Recruiter', 1),
(64, 'Sean',    'Chapman',    'sean.chapman@contoso.com',      '555-0164', '2022-06-13', 72000.00,  5,  14,   'HR Coordinator', 1),
-- Product team extras
(65, 'Diana',   'Reyes',      'diana.reyes@contoso.com',       '555-0165', '2021-05-01', 130000.00, 12, 19,   'Product Manager', 1),
(66, 'Felix',   'Dunn',       'felix.dunn@contoso.com',        '555-0166', '2022-02-15', 110000.00, 12, 20,   'Associate Product Manager', 1),
-- Terminated employees (for is_active queries)
(67, 'Paul',    'Hoffman',    'paul.hoffman@contoso.com',      '555-0167', '2020-01-06', 120000.00, 8,  5,    'Senior Engineer', 0),
(68, 'Wendy',   'Blake',      'wendy.blake@contoso.com',       '555-0168', '2020-08-17', 85000.00,  3,  9,    'Account Executive', 0),
(69, 'Carl',    'Moss',       'carl.moss@contoso.com',         '555-0169', '2021-02-01', 70000.00,  7,  18,   'Support Agent', 0),
(70, 'Nina',    'Wolfe',      'nina.wolfe@contoso.com',        '555-0170', '2021-06-14', 90000.00,  4,  12,   'Marketing Specialist', 0),
-- More engineers to fill out teams
(71, 'Derek',   'Flores',     'derek.flores@contoso.com',      '555-0171', '2022-09-01', 115000.00, 8,  23,   'Software Engineer', 1),
(72, 'Tessa',   'Long',       'tessa.long@contoso.com',        '555-0172', '2022-11-14', 108000.00, 9,  31,   'Software Engineer', 1),
(73, 'Hugo',    'Mendez',     'hugo.mendez@contoso.com',       '555-0173', '2023-01-09', 112000.00, 8,  21,   'Software Engineer', 1),
(74, 'Clara',   'Ortiz',      'clara.ortiz@contoso.com',       '555-0174', '2023-03-20', 105000.00, 10, 36,   'Data Engineer', 1),
(75, 'Victor',  'Nguyen',     'victor.nguyen@contoso.com',     '555-0175', '2023-06-05', 118000.00, 11, 41,   'Senior DevOps Engineer', 1),
(76, 'Alice',   'Park',       'alice.park@contoso.com',        '555-0176', '2023-08-14', 100000.00, 9,  31,   'Junior Engineer', 1),
(77, 'Brett',   'Sanders',    'brett.sanders@contoso.com',     '555-0177', '2023-10-01', 95000.00,  8,  22,   'Junior Engineer', 1),
(78, 'Iris',    'Fleming',    'iris.fleming@contoso.com',      '555-0178', '2024-01-08', 98000.00,  10, 7,    'Data Analyst', 1),
(79, 'Owen',    'Mccoy',      'owen.mccoy@contoso.com',        '555-0179', '2024-03-11', 72000.00,  7,  18,   'Support Agent', 1),
(80, 'June',    'Barker',     'june.barker@contoso.com',       '555-0180', '2024-05-20', 80000.00,  3,  10,   'Sales Development Rep', 1);
SET IDENTITY_INSERT hr.employees OFF;
GO

-- Set termination dates for inactive employees
UPDATE hr.employees SET termination_date = '2022-06-30' WHERE id = 67;
UPDATE hr.employees SET termination_date = '2022-03-15' WHERE id = 68;
UPDATE hr.employees SET termination_date = '2022-09-01' WHERE id = 69;
UPDATE hr.employees SET termination_date = '2022-12-31' WHERE id = 70;
GO

-- Set department managers
UPDATE hr.departments SET manager_employee_id = 1  WHERE id = 1;
UPDATE hr.departments SET manager_employee_id = 4  WHERE id = 2;
UPDATE hr.departments SET manager_employee_id = 8  WHERE id = 3;
UPDATE hr.departments SET manager_employee_id = 11 WHERE id = 4;
UPDATE hr.departments SET manager_employee_id = 13 WHERE id = 5;
UPDATE hr.departments SET manager_employee_id = 15 WHERE id = 6;
UPDATE hr.departments SET manager_employee_id = 17 WHERE id = 7;
UPDATE hr.departments SET manager_employee_id = 5  WHERE id = 8;
UPDATE hr.departments SET manager_employee_id = 6  WHERE id = 9;
UPDATE hr.departments SET manager_employee_id = 7  WHERE id = 10;
UPDATE hr.departments SET manager_employee_id = 40 WHERE id = 11;
UPDATE hr.departments SET manager_employee_id = 19 WHERE id = 12;
GO

-- 8.3  HR: Employee Addresses (one per employee for most, two for some)
INSERT INTO hr.employee_addresses (employee_id, address_type, street_address, city, state, postal_code, country) VALUES
(1,  'home', '100 Executive Dr',     'San Francisco', 'CA', '94105', 'US'),
(2,  'home', '200 Market St',        'San Francisco', 'CA', '94102', 'US'),
(3,  'home', '150 Financial Blvd',   'San Francisco', 'CA', '94111', 'US'),
(4,  'home', '42 Tech Lane',         'Seattle',       'WA', '98101', 'US'),
(5,  'home', '88 Code Ave',          'Seattle',       'WA', '98102', 'US'),
(6,  'home', '55 Frontend Way',      'Portland',      'OR', '97201', 'US'),
(7,  'home', '120 Data Blvd',        'Austin',        'TX', '73301', 'US'),
(8,  'home', '300 Sales Plaza',      'New York',      'NY', '10001', 'US'),
(8,  'mailing', '301 Sales Plaza',   'New York',      'NY', '10001', 'US'),
(9,  'home', '450 Commerce St',      'Chicago',       'IL', '60601', 'US'),
(10, 'home', '75 Trade Center',      'Atlanta',       'GA', '30301', 'US'),
(11, 'home', '900 Brand Ave',        'Los Angeles',   'CA', '90001', 'US'),
(12, 'home', '220 Media Row',        'Los Angeles',   'CA', '90002', 'US'),
(13, 'home', '500 People Way',       'San Francisco', 'CA', '94103', 'US'),
(15, 'home', '600 Ledger Lane',      'San Francisco', 'CA', '94104', 'US'),
(17, 'home', '700 Help Desk Dr',     'Denver',        'CO', '80201', 'US'),
(19, 'home', '850 Product Pkwy',     'San Francisco', 'CA', '94106', 'US'),
(21, 'home', '33 Backend Ct',        'Seattle',       'WA', '98103', 'US'),
(29, 'home', '77 React Rd',          'Portland',      'OR', '97202', 'US'),
(35, 'home', '101 Pipeline Dr',      'Austin',        'TX', '73302', 'US'),
(40, 'home', '12 Cloud Way',         'Denver',        'CO', '80202', 'US'),
(44, 'home', '160 Prospect Ave',     'Chicago',       'IL', '60602', 'US'),
(47, 'home', '280 Deal St',          'Atlanta',       'GA', '30302', 'US');
GO

-- 8.4  HR: Salary History
INSERT INTO hr.salary_history (employee_id, effective_date, old_salary, new_salary, change_reason) VALUES
-- CEO raises
(1,  '2019-01-15', 0,        220000.00, 'hire'),
(1,  '2020-01-01', 220000.00, 235000.00, 'annual_review'),
(1,  '2021-01-01', 235000.00, 250000.00, 'annual_review'),
-- VP Eng promotions
(4,  '2019-02-20', 0,        170000.00, 'hire'),
(4,  '2020-01-01', 170000.00, 180000.00, 'annual_review'),
(4,  '2021-01-01', 180000.00, 195000.00, 'promotion'),
(4,  '2022-01-01', 195000.00, 200000.00, 'annual_review'),
-- Backend staff engineer
(21, '2020-06-01', 0,        130000.00, 'hire'),
(21, '2021-01-01', 130000.00, 140000.00, 'annual_review'),
(21, '2022-01-01', 140000.00, 155000.00, 'promotion'),
-- Sales rep
(44, '2020-03-15', 0,        75000.00,  'hire'),
(44, '2021-01-01', 75000.00,  82000.00,  'annual_review'),
(44, '2022-01-01', 82000.00,  90000.00,  'promotion'),
(44, '2023-01-01', 90000.00,  95000.00,  'annual_review'),
-- Market adjustments for engineers
(22, '2020-08-15', 0,        120000.00, 'hire'),
(22, '2021-07-01', 120000.00, 135000.00, 'market_adjustment'),
(22, '2022-01-01', 135000.00, 145000.00, 'annual_review'),
(30, '2020-11-16', 0,        115000.00, 'hire'),
(30, '2021-07-01', 115000.00, 130000.00, 'market_adjustment'),
(30, '2022-01-01', 130000.00, 140000.00, 'annual_review'),
-- Support agent hire
(56, '2021-01-18', 0,        60000.00,  'hire'),
(56, '2022-01-01', 60000.00,  65000.00,  'annual_review'),
(56, '2023-01-01', 65000.00,  68000.00,  'annual_review'),
-- Role changes
(36, '2021-01-15', 0,        120000.00, 'hire'),
(36, '2022-01-01', 120000.00, 130000.00, 'annual_review'),
(36, '2023-01-01', 130000.00, 140000.00, 'role_change');
GO

-- 8.5  Sales: Regions & Territories
SET IDENTITY_INSERT sales.regions ON;
INSERT INTO sales.regions (id, name, country) VALUES
(1, 'Northeast',  'US'),
(2, 'Southeast',  'US'),
(3, 'Midwest',    'US'),
(4, 'West',       'US'),
(5, 'Northwest',  'US'),
(6, 'Southwest',  'US'),
(7, 'UK',         'GB'),
(8, 'DACH',       'DE');
SET IDENTITY_INSERT sales.regions OFF;
GO

SET IDENTITY_INSERT sales.territories ON;
INSERT INTO sales.territories (id, name, region_id) VALUES
(1,  'New York Metro',       1),
(2,  'New England',          1),
(3,  'Mid-Atlantic',         1),
(4,  'Florida',              2),
(5,  'Carolinas',            2),
(6,  'Georgia & Alabama',    2),
(7,  'Great Lakes',          3),
(8,  'Plains',               3),
(9,  'Texas',                6),
(10, 'Southern California',  4),
(11, 'Northern California',  4),
(12, 'Pacific Northwest',    5),
(13, 'Mountain',             5),
(14, 'Arizona & Nevada',     6),
(15, 'London & South',       7),
(16, 'Midlands & North',     7),
(17, 'DACH Metro',           8),
(18, 'Ohio Valley',          3),
(19, 'Hawaii & Pacific',     4),
(20, 'New York Upstate',     1);
SET IDENTITY_INSERT sales.territories OFF;
GO

-- 8.6  Inventory: Categories (hierarchical)
SET IDENTITY_INSERT inventory.categories ON;
INSERT INTO inventory.categories (id, name, description, parent_category_id) VALUES
(1,  'Electronics',        'Electronic devices and accessories',     NULL),
(2,  'Computers',          'Laptops, desktops, and accessories',     1),
(3,  'Smartphones',        'Mobile phones and accessories',          1),
(4,  'Audio',              'Headphones, speakers, earbuds',          1),
(5,  'Furniture',          'Office and home furniture',              NULL),
(6,  'Desks',              'Standing desks, sit-stand, traditional', 5),
(7,  'Chairs',             'Ergonomic, gaming, executive chairs',    5),
(8,  'Storage',            'Shelving, cabinets, organizers',         5),
(9,  'Clothing',           'Apparel and accessories',                NULL),
(10, 'Outerwear',          'Jackets, coats, vests',                  9),
(11, 'Tops',               'Shirts, blouses, sweaters',              9),
(12, 'Bottoms',            'Pants, shorts, skirts',                  9),
(13, 'Kitchen',            'Kitchen appliances and tools',           NULL),
(14, 'Appliances',         'Small kitchen appliances',               13),
(15, 'Cookware',           'Pots, pans, bakeware',                  13),
(16, 'Books',              'Physical and digital books',             NULL),
(17, 'Technical',          'Programming and engineering books',      16),
(18, 'Business',           'Management and strategy books',          16),
(19, 'Sports & Outdoors',  'Athletic gear and outdoor equipment',    NULL),
(20, 'Fitness',            'Gym equipment and accessories',          19),
(21, 'Camping',            'Tents, sleeping bags, gear',             19),
(22, 'Tablets',            'Tablet devices and accessories',         1),
(23, 'Networking',         'Routers, switches, cables',              1);
SET IDENTITY_INSERT inventory.categories OFF;
GO

-- 8.7  Inventory: Products (150 products)
SET IDENTITY_INSERT inventory.products ON;
INSERT INTO inventory.products (id, name, sku, category_id, unit_price, cost_price, weight_kg, is_discontinued) VALUES
-- Computers (cat 2)
(1,   'ProBook Laptop 15"',            'COMP-001', 2,  1299.99, 780.00,  2.1,  0),
(2,   'ProBook Laptop 13"',            'COMP-002', 2,  1099.99, 660.00,  1.4,  0),
(3,   'UltraDesk Desktop',             'COMP-003', 2,  1599.99, 950.00,  8.5,  0),
(4,   'ProBook Chromebook',            'COMP-004', 2,  449.99,  270.00,  1.2,  0),
(5,   'External SSD 1TB',              'COMP-005', 2,  129.99,  65.00,   0.1,  0),
(6,   'External SSD 2TB',              'COMP-006', 2,  219.99,  110.00,  0.1,  0),
(7,   'USB-C Docking Station',         'COMP-007', 2,  179.99,  90.00,   0.4,  0),
(8,   'Wireless Keyboard',             'COMP-008', 2,  79.99,   35.00,   0.5,  0),
(9,   'Wireless Mouse',                'COMP-009', 2,  49.99,   20.00,   0.1,  0),
(10,  '27" 4K Monitor',                'COMP-010', 2,  549.99,  330.00,  6.2,  0),
(11,  '32" Curved Monitor',            'COMP-011', 2,  699.99,  420.00,  7.8,  0),
(12,  'Webcam HD Pro',                 'COMP-012', 2,  99.99,   45.00,   0.2,  0),
(13,  'ProBook Laptop 17"',            'COMP-013', 2,  1499.99, 900.00,  2.8,  1),
-- Smartphones (cat 3)
(14,  'Galaxy Phone X',                'PHON-001', 3,  999.99,  600.00,  0.2,  0),
(15,  'Galaxy Phone SE',               'PHON-002', 3,  599.99,  360.00,  0.2,  0),
(16,  'Phone Case - Rugged',           'PHON-003', 3,  39.99,   12.00,   0.1,  0),
(17,  'Screen Protector 3-Pack',       'PHON-004', 3,  14.99,   3.00,    0.05, 0),
(18,  'Wireless Charger Pad',          'PHON-005', 3,  29.99,   12.00,   0.2,  0),
(19,  'Car Phone Mount',               'PHON-006', 3,  24.99,   8.00,    0.15, 0),
-- Audio (cat 4)
(20,  'NoiseCancel Pro Headphones',    'AUD-001',  4,  349.99,  175.00,  0.3,  0),
(21,  'Wireless Earbuds Pro',          'AUD-002',  4,  199.99,  80.00,   0.05, 0),
(22,  'Bluetooth Speaker M',          'AUD-003',  4,  89.99,   40.00,   0.6,  0),
(23,  'Bluetooth Speaker L',          'AUD-004',  4,  149.99,  70.00,   1.2,  0),
(24,  'Studio Monitor Headphones',     'AUD-005',  4,  249.99,  120.00,  0.35, 0),
(25,  'Portable DAC/Amp',             'AUD-006',  4,  129.99,  55.00,   0.1,  0),
-- Tablets (cat 22)
(26,  'ProTab 11"',                    'TAB-001',  22, 799.99,  480.00,  0.5,  0),
(27,  'ProTab 13"',                    'TAB-002',  22, 1099.99, 660.00,  0.7,  0),
(28,  'Stylus Pen Pro',               'TAB-003',  22, 129.99,  40.00,   0.02, 0),
(29,  'Tablet Keyboard Case',         'TAB-004',  22, 149.99,  60.00,   0.3,  0),
-- Networking (cat 23)
(30,  'WiFi 6E Router',               'NET-001',  23, 249.99,  120.00,  0.8,  0),
(31,  'Mesh WiFi System 3-Pack',      'NET-002',  23, 399.99,  200.00,  1.5,  0),
(32,  'Ethernet Switch 8-Port',       'NET-003',  23, 49.99,   22.00,   0.4,  0),
(33,  'Cat6 Cable 50ft',              'NET-004',  23, 19.99,   5.00,    0.3,  0),
-- Desks (cat 6)
(34,  'Standing Desk Pro',            'DESK-001', 6,  699.99,  350.00,  35.0, 0),
(35,  'Sit-Stand Desk Converter',     'DESK-002', 6,  349.99,  175.00,  12.0, 0),
(36,  'Executive L-Desk',             'DESK-003', 6,  899.99,  450.00,  45.0, 0),
(37,  'Compact Writing Desk',         'DESK-004', 6,  249.99,  125.00,  18.0, 0),
-- Chairs (cat 7)
(38,  'Ergonomic Mesh Chair',         'CHR-001',  7,  549.99,  275.00,  15.0, 0),
(39,  'Executive Leather Chair',      'CHR-002',  7,  799.99,  400.00,  22.0, 0),
(40,  'Gaming Chair Pro',             'CHR-003',  7,  449.99,  225.00,  20.0, 0),
(41,  'Task Chair Basic',             'CHR-004',  7,  199.99,  100.00,  10.0, 0),
-- Storage (cat 8)
(42,  'Bookshelf 5-Tier',             'STOR-001', 8,  149.99,  75.00,   12.0, 0),
(43,  'Filing Cabinet 3-Drawer',      'STOR-002', 8,  249.99,  125.00,  25.0, 0),
(44,  'Desk Organizer Set',           'STOR-003', 8,  34.99,   15.00,   1.0,  0),
-- Outerwear (cat 10)
(45,  'All-Weather Jacket',           'CLO-001',  10, 189.99,  80.00,   0.8,  0),
(46,  'Lightweight Down Vest',        'CLO-002',  10, 129.99,  55.00,   0.4,  0),
(47,  'Rain Shell',                   'CLO-003',  10, 99.99,   42.00,   0.3,  0),
(48,  'Fleece Pullover',              'CLO-004',  10, 69.99,   30.00,   0.5,  0),
-- Tops (cat 11)
(49,  'Performance Polo',             'CLO-005',  11, 54.99,   22.00,   0.2,  0),
(50,  'Oxford Button-Down',           'CLO-006',  11, 64.99,   28.00,   0.25, 0),
(51,  'Merino Wool Sweater',          'CLO-007',  11, 119.99,  50.00,   0.4,  0),
(52,  'Graphic Tee',                  'CLO-008',  11, 29.99,   10.00,   0.15, 0),
-- Bottoms (cat 12)
(53,  'Chino Pants',                  'CLO-009',  12, 59.99,   25.00,   0.4,  0),
(54,  'Performance Joggers',          'CLO-010',  12, 49.99,   20.00,   0.3,  0),
(55,  'Cargo Shorts',                 'CLO-011',  12, 39.99,   16.00,   0.3,  0),
-- Appliances (cat 14)
(56,  'Espresso Machine',             'KIT-001',  14, 499.99,  250.00,  6.0,  0),
(57,  'Blender Pro',                  'KIT-002',  14, 129.99,  55.00,   3.5,  0),
(58,  'Air Fryer XL',                 'KIT-003',  14, 149.99,  65.00,   5.0,  0),
(59,  'Toaster 4-Slice',              'KIT-004',  14, 49.99,   22.00,   2.0,  0),
(60,  'Electric Kettle',              'KIT-005',  14, 39.99,   16.00,   1.0,  0),
(61,  'Stand Mixer',                  'KIT-006',  14, 349.99,  175.00,  10.0, 0),
-- Cookware (cat 15)
(62,  'Cast Iron Skillet 12"',        'KIT-007',  15, 44.99,   18.00,   3.5,  0),
(63,  'Non-Stick Pan Set 3pc',        'KIT-008',  15, 79.99,   35.00,   4.0,  0),
(64,  'Stainless Steel Pot Set 5pc',  'KIT-009',  15, 199.99,  90.00,   8.0,  0),
(65,  'Baking Sheet Set',             'KIT-010',  15, 29.99,   12.00,   2.0,  0),
-- Technical Books (cat 17)
(66,  'Designing Data-Intensive Apps', 'BOOK-001', 17, 49.99,   20.00,   0.8,  0),
(67,  'Clean Code',                    'BOOK-002', 17, 39.99,   16.00,   0.7,  0),
(68,  'System Design Interview',       'BOOK-003', 17, 35.99,   14.00,   0.6,  0),
(69,  'SQL Performance Explained',     'BOOK-004', 17, 44.99,   18.00,   0.5,  0),
(70,  'Python for Data Analysis',      'BOOK-005', 17, 54.99,   22.00,   0.9,  0),
-- Business Books (cat 18)
(71,  'The Lean Startup',              'BOOK-006', 18, 24.99,   10.00,   0.4,  0),
(72,  'Good to Great',                 'BOOK-007', 18, 19.99,   8.00,    0.35, 0),
(73,  'Measure What Matters',          'BOOK-008', 18, 27.99,   11.00,   0.4,  0),
-- Fitness (cat 20)
(74,  'Yoga Mat Premium',             'FIT-001',  20, 49.99,   20.00,   1.5,  0),
(75,  'Resistance Band Set',          'FIT-002',  20, 29.99,   10.00,   0.5,  0),
(76,  'Adjustable Dumbbells',         'FIT-003',  20, 299.99,  150.00,  22.0, 0),
(77,  'Jump Rope Speed',              'FIT-004',  20, 19.99,   6.00,    0.2,  0),
(78,  'Foam Roller',                  'FIT-005',  20, 24.99,   8.00,    0.5,  0),
-- Camping (cat 21)
(79,  '2-Person Tent',                'CAMP-001', 21, 199.99,  90.00,   2.5,  0),
(80,  'Sleeping Bag 30F',             'CAMP-002', 21, 89.99,   40.00,   1.8,  0),
(81,  'Camping Stove Portable',       'CAMP-003', 21, 59.99,   25.00,   0.9,  0),
(82,  'Headlamp LED 600lm',          'CAMP-004', 21, 34.99,   14.00,   0.1,  0),
(83,  'Water Filter Portable',        'CAMP-005', 21, 44.99,   18.00,   0.3,  0),
-- More electronics accessories
(84,  'Laptop Sleeve 15"',            'ACC-001',  2,  29.99,   10.00,   0.2,  0),
(85,  'USB-C Hub 7-in-1',             'ACC-002',  2,  59.99,   25.00,   0.15, 0),
(86,  'Surge Protector 12-Outlet',    'ACC-003',  1,  39.99,   16.00,   0.8,  0),
(87,  'UPS Battery Backup 1000VA',    'ACC-004',  1,  159.99,  80.00,   8.0,  0),
-- Discontinued items
(88,  'ProBook Laptop 14" (2022)',     'COMP-014', 2,  999.99,  600.00,  1.8,  1),
(89,  'Basic Wired Mouse',            'COMP-015', 2,  14.99,   5.00,    0.1,  1),
(90,  'DVD-R 50-Pack',                'COMP-016', 2,  19.99,   5.00,    0.5,  1),
-- Additional products to reach ~150
(91,  'Laptop Stand Adjustable',      'ACC-005',  2,  44.99,   18.00,   1.2,  0),
(92,  'Monitor Light Bar',            'ACC-006',  2,  69.99,   30.00,   0.5,  0),
(93,  'Desk Mat XXL',                 'ACC-007',  5,  24.99,   8.00,    0.6,  0),
(94,  'Cable Management Kit',         'ACC-008',  5,  19.99,   6.00,    0.3,  0),
(95,  'Power Strip USB 6-Port',       'ACC-009',  1,  34.99,   14.00,   0.5,  0),
(96,  'Portable Monitor 15.6"',       'COMP-017', 2,  299.99,  150.00,  0.8,  0),
(97,  'Thunderbolt 4 Cable 2m',       'ACC-010',  23, 39.99,   15.00,   0.1,  0),
(98,  'Smart Plug 4-Pack',            'ACC-011',  1,  29.99,   12.00,   0.4,  0),
(99,  'Desk Lamp LED',                'ACC-012',  5,  59.99,   25.00,   1.5,  0),
(100, 'Whiteboard 48x36',             'ACC-013',  5,  89.99,   40.00,   5.0,  0),
(101, 'Noise Machine',                'ACC-014',  4,  39.99,   16.00,   0.3,  0),
(102, 'Webcam Ring Light',            'ACC-015',  2,  24.99,   8.00,    0.2,  0),
(103, 'Microphone USB Condenser',     'AUD-007',  4,  79.99,   35.00,   0.5,  0),
(104, 'Microphone Boom Arm',          'AUD-008',  4,  39.99,   16.00,   0.8,  0),
(105, 'Pop Filter',                   'AUD-009',  4,  12.99,   4.00,    0.1,  0),
(106, 'Audio Interface USB',          'AUD-010',  4,  149.99,  65.00,   0.4,  0),
(107, 'Studio Foam Panels 12-Pack',   'AUD-011',  4,  49.99,   20.00,   2.0,  0),
(108, 'Travel Backpack 40L',          'CAMP-006', 21, 79.99,   35.00,   1.2,  0),
(109, 'Insulated Water Bottle 32oz',  'CAMP-007', 21, 34.99,   14.00,   0.4,  0),
(110, 'Trekking Poles Pair',          'CAMP-008', 21, 69.99,   30.00,   0.5,  0),
(111, 'Compression Socks 3-Pack',     'FIT-006',  20, 24.99,   8.00,    0.2,  0),
(112, 'Kettlebell 35lb',              'FIT-007',  20, 54.99,   25.00,   16.0, 0),
(113, 'Pull-Up Bar Doorway',          'FIT-008',  20, 34.99,   14.00,   2.5,  0),
(114, 'Running Belt',                 'FIT-009',  20, 19.99,   6.00,    0.1,  0),
(115, 'Gym Bag Duffel',              'FIT-010',  20, 44.99,   18.00,   0.8,  0),
(116, 'Stainless Travel Mug',         'KIT-011',  13, 24.99,   8.00,    0.3,  0),
(117, 'French Press 34oz',            'KIT-012',  13, 29.99,   12.00,   0.7,  0),
(118, 'Pour Over Coffee Set',         'KIT-013',  13, 39.99,   16.00,   0.5,  0),
(119, 'Knife Set 8-Piece',            'KIT-014',  15, 149.99,  65.00,   3.0,  0),
(120, 'Cutting Board Bamboo',         'KIT-015',  15, 24.99,   8.00,    1.2,  0),
(121, 'Apron Cotton',                 'KIT-016',  13, 19.99,   6.00,    0.2,  0),
(122, 'Linen Shirt',                  'CLO-012',  11, 79.99,   35.00,   0.25, 0),
(123, 'Denim Jacket',                 'CLO-013',  10, 99.99,   42.00,   0.9,  0),
(124, 'Wool Beanie',                  'CLO-014',  9,  24.99,   8.00,    0.1,  0),
(125, 'Leather Belt',                 'CLO-015',  9,  44.99,   18.00,   0.2,  0),
(126, 'Sunglasses Polarized',         'CLO-016',  9,  59.99,   22.00,   0.05, 0),
(127, 'Canvas Sneakers',              'CLO-017',  9,  64.99,   28.00,   0.6,  0),
(128, 'Wool Socks 6-Pack',            'CLO-018',  9,  34.99,   12.00,   0.3,  0),
(129, 'Machine Learning Yearning',    'BOOK-009', 17, 29.99,   12.00,   0.3,  0),
(130, 'Database Internals',           'BOOK-010', 17, 54.99,   22.00,   0.7,  0),
(131, 'Atomic Habits',                'BOOK-011', 18, 22.99,   9.00,    0.3,  0),
(132, 'Zero to One',                  'BOOK-012', 18, 21.99,   9.00,    0.3,  0),
(133, 'Thinking Fast and Slow',       'BOOK-013', 18, 18.99,   7.00,    0.4,  0),
(134, 'Monitor Arm Dual',             'ACC-016',  5,  129.99,  55.00,   3.0,  0),
(135, 'Monitor Arm Single',           'ACC-017',  5,  69.99,   30.00,   1.8,  0),
(136, 'Footrest Ergonomic',           'ACC-018',  5,  44.99,   18.00,   2.0,  0),
(137, 'Privacy Screen 27"',           'ACC-019',  2,  49.99,   20.00,   0.3,  0),
(138, 'Wrist Rest Keyboard',          'ACC-020',  2,  19.99,   6.00,    0.2,  0),
(139, 'Wrist Rest Mouse',             'ACC-021',  2,  14.99,   4.00,    0.1,  0),
(140, 'Portable Projector',           'COMP-018', 2,  399.99,  200.00,  1.2,  0),
(141, 'Drawing Tablet',               'COMP-019', 2,  249.99,  120.00,  0.6,  0),
(142, 'E-Reader',                     'COMP-020', 2,  139.99,  70.00,   0.2,  0),
(143, 'Fitness Tracker Band',         'FIT-011',  20, 79.99,   35.00,   0.05, 0),
(144, 'Ab Roller',                    'FIT-012',  20, 19.99,   6.00,    0.5,  0),
(145, 'Meditation Cushion',           'FIT-013',  20, 39.99,   16.00,   1.0,  0),
(146, 'Hammock Portable',             'CAMP-009', 21, 49.99,   20.00,   0.6,  0),
(147, 'First Aid Kit Compact',        'CAMP-010', 21, 24.99,   10.00,   0.3,  0),
(148, 'Solar Charger Panel',          'CAMP-011', 21, 59.99,   25.00,   0.4,  0),
(149, 'Insect Repellent Spray 6oz',   'CAMP-012', 21, 9.99,    3.00,    0.2,  0),
(150, 'Compact Binoculars',           'CAMP-013', 21, 89.99,   40.00,   0.4,  0);
SET IDENTITY_INSERT inventory.products OFF;
GO

-- 8.8  Inventory: Suppliers
SET IDENTITY_INSERT inventory.suppliers ON;
INSERT INTO inventory.suppliers (id, company_name, contact_name, email, phone, country, reliability_rating) VALUES
(1,  'TechSource Global',      'Wei Liu',          'wei@techsource.com',        '+86-10-5550101',  'CN', 5),
(2,  'Pacific Components',     'Akiko Sato',       'akiko@paccomp.jp',          '+81-3-5550102',   'JP', 4),
(3,  'EuroElectro GmbH',       'Hans Mueller',     'hans@euroelectro.de',       '+49-30-5550103',  'DE', 4),
(4,  'AmeriSupply Co',         'John Blake',       'john@amerisupply.com',      '555-0201',        'US', 5),
(5,  'FurniCraft Ltd',         'Emma Wilson',      'emma@furnicraft.co.uk',     '+44-20-5550105',  'GB', 4),
(6,  'TextilePro India',       'Ravi Kapoor',      'ravi@textilepro.in',        '+91-11-5550106',  'IN', 3),
(7,  'GreenGear Outdoors',     'Lars Svensson',    'lars@greengear.se',         '+46-8-5550107',   'SE', 5),
(8,  'KitchenWorks Taiwan',    'Ming Chen',        'ming@kitchenworks.tw',      '+886-2-5550108',  'TW', 4),
(9,  'BookPrint Partners',     'Sarah Jones',      'sarah@bookprint.com',       '555-0209',        'US', 5),
(10, 'SilverLine Audio',       'Marco Bianchi',    'marco@silverline.it',       '+39-02-5550110',  'IT', 4),
(11, 'ShenzhenTech Direct',    'Li Wei',           'liwei@shenzhentech.cn',     '+86-755-5550111', 'CN', 3),
(12, 'Nordic Fitness AB',      'Erik Johansson',   'erik@nordicfitness.se',     '+46-8-5550112',   'SE', 4),
(13, 'MexiCraft Textiles',     'Carlos Ramirez',   'carlos@mexicraft.mx',       '+52-55-5550113',  'MX', 3),
(14, 'VietnamMfg Corp',        'Tran Nguyen',      'tran@vietnammfg.vn',        '+84-28-5550114',  'VN', 4),
(15, 'CanadianWood Inc',       'Jennifer Maple',   'jennifer@canwood.ca',       '+1-604-5550115',  'CA', 5),
(16, 'BrasilParts Ltda',       'Roberto Silva',    'roberto@brasilparts.br',    '+55-11-5550116',  'BR', 3),
(17, 'AussieGear Pty Ltd',     'Jack Thompson',    'jack@aussiegear.au',        '+61-2-5550117',   'AU', 4),
(18, 'KoreaChip Inc',          'Joon Park',        'joon@koreachip.kr',         '+82-2-5550118',   'KR', 5),
(19, 'PolandPack Sp z.o.o.',   'Piotr Nowak',      'piotr@polandpack.pl',       '+48-22-5550119',  'PL', 4),
(20, 'IsraelTech Solutions',   'David Cohen',      'david@israeltech.il',       '+972-3-5550120',  'IL', 5);
SET IDENTITY_INSERT inventory.suppliers OFF;
GO

-- 8.9  Inventory: Product-Supplier mappings (select products with 1-3 suppliers each)
INSERT INTO inventory.product_suppliers (product_id, supplier_id, lead_time_days, supply_cost) VALUES
(1,  1,  21, 750.00), (1,  2,  28, 770.00),
(2,  1,  21, 640.00), (2,  18, 18, 650.00),
(3,  1,  25, 920.00), (3,  4,  10, 960.00),
(5,  18, 14, 60.00),  (6,  18, 14, 105.00),
(7,  11, 18, 85.00),  (8,  11, 18, 32.00),
(9,  11, 18, 18.00),  (10, 2,  21, 320.00),
(11, 2,  21, 410.00), (14, 18, 14, 580.00),
(15, 18, 14, 350.00), (20, 10, 21, 170.00),
(21, 10, 21, 75.00),  (22, 10, 21, 38.00),
(26, 1,  21, 460.00), (27, 1,  21, 640.00),
(30, 11, 18, 115.00), (31, 11, 18, 190.00),
(34, 5,  14, 340.00), (34, 15, 10, 355.00),
(35, 5,  14, 170.00), (36, 15, 12, 440.00),
(38, 5,  14, 265.00), (39, 5,  14, 390.00),
(40, 14, 21, 220.00), (45, 6,  25, 75.00),
(46, 6,  25, 52.00),  (47, 14, 21, 40.00),
(49, 6,  25, 20.00),  (50, 13, 21, 26.00),
(56, 8,  18, 240.00), (57, 8,  18, 52.00),
(58, 8,  18, 62.00),  (61, 8,  18, 170.00),
(62, 4,  7,  16.00),  (63, 8,  18, 33.00),
(64, 8,  18, 85.00),  (66, 9,  5,  18.00),
(67, 9,  5,  14.00),  (68, 9,  5,  12.00),
(69, 9,  5,  16.00),  (70, 9,  5,  20.00),
(74, 12, 14, 18.00),  (75, 12, 14, 9.00),
(76, 12, 14, 145.00), (79, 7,  10, 85.00),
(80, 7,  10, 38.00),  (81, 7,  10, 23.00),
(86, 4,  7,  14.00),  (87, 4,  7,  75.00),
(103,10, 21, 33.00),  (106,10, 21, 62.00);
GO

-- 8.10  Inventory: Warehouses
SET IDENTITY_INSERT inventory.warehouses ON;
INSERT INTO inventory.warehouses (id, name, city, state, country, capacity_units) VALUES
(1, 'East Coast Hub',     'Newark',        'NJ', 'US', 50000),
(2, 'West Coast Hub',     'Ontario',       'CA', 'US', 60000),
(3, 'Central Warehouse',  'Dallas',        'TX', 'US', 40000),
(4, 'Southeast Depot',    'Atlanta',       'GA', 'US', 30000),
(5, 'UK Warehouse',       'Birmingham',    NULL, 'GB', 25000);
SET IDENTITY_INSERT inventory.warehouses OFF;
GO

-- 8.11  Inventory: Stock Levels (generate for ~40 popular products across warehouses)
INSERT INTO inventory.stock_levels (product_id, warehouse_id, quantity_on_hand, reorder_point, last_restocked_at) VALUES
-- Computers & accessories across all US warehouses
(1,  1, 120, 50,  '2026-03-01'), (1,  2, 200, 50,  '2026-03-05'), (1,  3, 80,  50,  '2026-02-20'),
(2,  1, 150, 40,  '2026-03-10'), (2,  2, 180, 40,  '2026-03-08'),
(3,  1, 45,  30,  '2026-02-15'), (3,  2, 60,  30,  '2026-02-28'),
(5,  1, 300, 100, '2026-03-15'), (5,  2, 350, 100, '2026-03-12'), (5,  3, 200, 100, '2026-03-01'),
(10, 1, 75,  30,  '2026-03-01'), (10, 2, 90,  30,  '2026-03-05'),
(11, 1, 40,  20,  '2026-02-20'), (11, 2, 55,  20,  '2026-02-25'),
-- Audio products
(20, 1, 200, 80,  '2026-03-10'), (20, 2, 250, 80,  '2026-03-08'), (20, 5, 100, 40, '2026-03-01'),
(21, 1, 350, 100, '2026-03-12'), (21, 2, 400, 100, '2026-03-10'),
-- Phones
(14, 1, 100, 40,  '2026-03-15'), (14, 2, 130, 40,  '2026-03-12'),
(15, 1, 180, 60,  '2026-03-10'), (15, 2, 200, 60,  '2026-03-08'),
-- Furniture (heavy, fewer per warehouse)
(34, 1, 25,  15,  '2026-02-01'), (34, 2, 30,  15,  '2026-02-10'), (34, 3, 20, 15, '2026-01-28'),
(38, 1, 35,  20,  '2026-02-15'), (38, 2, 40,  20,  '2026-02-20'),
(39, 1, 15,  10,  '2026-01-20'), (39, 2, 18,  10,  '2026-01-25'),
-- Low stock items (for v_low_stock_alerts testing)
(22, 1, 5,   30,  '2025-12-15'), (22, 3, 8,   30,  '2025-12-20'),
(40, 4, 3,   10,  '2025-11-01'),
(56, 1, 2,   15,  '2025-10-20'), (56, 2, 4,   15,  '2025-11-05'),
(79, 3, 1,   10,  '2025-09-15'),
(62, 1, 7,   25,  '2025-12-01'), (62, 3, 4,   25,  '2025-11-15'),
-- Books
(66, 1, 500, 100, '2026-03-01'), (67, 1, 450, 100, '2026-03-01'),
(68, 1, 400, 100, '2026-02-15'), (69, 1, 200, 50,  '2026-02-20'),
-- Clothing
(45, 2, 180, 50,  '2026-03-05'), (49, 2, 250, 80,  '2026-03-10'),
(53, 2, 200, 60,  '2026-03-01'),
-- Kitchen
(57, 1, 120, 40,  '2026-03-10'), (58, 1, 100, 35,  '2026-03-08'),
(60, 1, 250, 80,  '2026-03-12'), (60, 3, 180, 80,  '2026-03-01'),
-- Fitness & camping
(74, 2, 300, 80,  '2026-03-10'), (76, 2, 25,  15,  '2026-02-15'),
(80, 3, 60,  20,  '2026-03-01'), (108,2, 150, 50,  '2026-03-05'),
-- UK warehouse stock
(1,  5, 50,  20,  '2026-02-25'), (2,  5, 60,  20,  '2026-03-01'),
(14, 5, 40,  15,  '2026-03-05'), (21, 5, 80,  30,  '2026-03-02'),
(45, 5, 70,  25,  '2026-02-28'), (66, 5, 100, 30,  '2026-03-01');
GO

-- 8.12  Sales: Customers (500)
-- We generate using a CTE with cross-joins for volume.
-- First insert 100 hand-crafted customers, then generate 400 more programmatically.

SET IDENTITY_INSERT sales.customers ON;
INSERT INTO sales.customers (id, first_name, last_name, email, phone, company_name, territory_id, customer_type, credit_limit, created_at) VALUES
(1,   'Alice',    'Morgan',     'alice.morgan@techcorp.com',     '555-1001', 'TechCorp Inc',         1,  'B2B', 50000.00,  '2023-01-15'),
(2,   'Bob',      'Chen',       'bob.chen@startuplab.io',        '555-1002', 'Startup Lab',          11, 'B2B', 25000.00,  '2023-01-20'),
(3,   'Carol',    'Davis',      'carol.davis@email.com',         '555-1003', NULL,                   4,  'B2C', NULL,       '2023-02-01'),
(4,   'Dan',      'Evans',      'dan.evans@megacorp.com',        '555-1004', 'MegaCorp Ltd',         15, 'B2B', 100000.00, '2023-02-10'),
(5,   'Eva',      'Fischer',    'eva.fischer@dach-gmbh.de',      '555-1005', 'DACH GmbH',            17, 'B2B', 75000.00,  '2023-02-15'),
(6,   'Frank',    'Green',      'frank.green@email.com',         '555-1006', NULL,                   7,  'B2C', NULL,       '2023-02-20'),
(7,   'Grace',    'Hill',       'grace.hill@innovatech.com',     '555-1007', 'InnovaTech',           9,  'B2B', 40000.00,  '2023-03-01'),
(8,   'Henry',    'Ito',        'henry.ito@email.com',           '555-1008', NULL,                   12, 'B2C', NULL,       '2023-03-05'),
(9,   'Irene',    'Jackson',    'irene.jackson@govworks.gov',    '555-1009', 'GovWorks Agency',      3,  'B2B', 200000.00, '2023-03-10'),
(10,  'Jake',     'Kumar',      'jake.kumar@dataflow.ai',        '555-1010', 'DataFlow AI',          10, 'B2B', 60000.00,  '2023-03-15'),
(11,  'Karen',    'Lopez',      'karen.lopez@email.com',         '555-1011', NULL,                   6,  'B2C', NULL,       '2023-03-20'),
(12,  'Leo',      'Martin',     'leo.martin@cloudnine.io',       '555-1012', 'Cloud Nine Inc',       2,  'B2B', 35000.00,  '2023-04-01'),
(13,  'Mia',      'Nelson',     'mia.nelson@email.com',          '555-1013', NULL,                   8,  'B2C', NULL,       '2023-04-05'),
(14,  'Nick',     'Olsen',      'nick.olsen@nordicdesign.se',    '555-1014', 'Nordic Design AB',     15, 'B2B', 45000.00,  '2023-04-10'),
(15,  'Olivia',   'Park',       'olivia.park@email.com',         '555-1015', NULL,                   5,  'B2C', NULL,       '2023-04-15'),
(16,  'Pete',     'Quinn',      'pete.quinn@builtright.com',     '555-1016', 'BuiltRight LLC',       7,  'B2B', 30000.00,  '2023-04-20'),
(17,  'Quinn',    'Reed',       'quinn.reed@email.com',          '555-1017', NULL,                   13, 'B2C', NULL,       '2023-05-01'),
(18,  'Rosa',     'Smith',      'rosa.smith@healthfirst.org',    '555-1018', 'HealthFirst',          9,  'B2B', 80000.00,  '2023-05-05'),
(19,  'Sam',      'Taylor',     'sam.taylor@email.com',          '555-1019', NULL,                   14, 'B2C', NULL,       '2023-05-10'),
(20,  'Tina',     'Ueda',       'tina.ueda@finsolve.com',        '555-1020', 'FinSolve Corp',        1,  'B2B', 55000.00,  '2023-05-15'),
(21,  'Uma',      'Varga',      'uma.varga@email.com',           '555-1021', NULL,                   16, 'B2C', NULL,       '2023-05-20'),
(22,  'Vic',      'Wang',       'vic.wang@globalship.com',       '555-1022', 'GlobalShip LLC',       10, 'B2B', 90000.00,  '2023-06-01'),
(23,  'Wendy',    'Xavier',     'wendy.xavier@email.com',        '555-1023', NULL,                   4,  'B2C', NULL,       '2023-06-05'),
(24,  'Xander',   'Young',      'xander.young@edgeai.io',        '555-1024', 'EdgeAI',               11, 'B2B', 70000.00,  '2023-06-10'),
(25,  'Yara',     'Zhang',      'yara.zhang@email.com',          '555-1025', NULL,                   18, 'B2C', NULL,       '2023-06-15'),
(26,  'Zane',     'Adams',      'zane.adams@constructco.com',    '555-1026', 'Construct Co',         3,  'B2B', 45000.00,  '2023-06-20'),
(27,  'Amber',    'Barnes',     'amber.barnes@email.com',        '555-1027', NULL,                   12, 'B2C', NULL,       '2023-07-01'),
(28,  'Blake',    'Cruz',       'blake.cruz@retailmax.com',      '555-1028', 'RetailMax',            6,  'B2B', 65000.00,  '2023-07-05'),
(29,  'Cora',     'Diaz',       'cora.diaz@email.com',           '555-1029', NULL,                   2,  'B2C', NULL,       '2023-07-10'),
(30,  'Drew',     'Ellis',      'drew.ellis@mediagroup.com',     '555-1030', 'Media Group Inc',      1,  'B2B', 55000.00,  '2023-07-15');
SET IDENTITY_INSERT sales.customers OFF;
GO

-- Generate remaining 470 customers programmatically
;WITH first_names AS (
    SELECT n, ROW_NUMBER() OVER (ORDER BY n) AS rn FROM (VALUES
    ('Aaron'),('Adrian'),('Aiden'),('Alan'),('Albert'),('Alexander'),('Andrea'),('Andrew'),
    ('Angela'),('Anna'),('Anthony'),('Arthur'),('Barbara'),('Benjamin'),('Beth'),('Brandon'),
    ('Brian'),('Bruce'),('Cameron'),('Carlos'),('Catherine'),('Charles'),('Charlotte'),('Chris'),
    ('Clara'),('Claudia'),('Colin'),('Connor'),('Craig'),('Curtis'),('Damon'),('Danielle'),
    ('Darren'),('David'),('Dean'),('Derek'),('Diana'),('Donald'),('Dorothy'),('Douglas'),
    ('Edward'),('Eleanor'),('Elizabeth'),('Eric'),('Evan'),('Fiona'),('Florence'),('Gabriel')
    ) AS t(n)
),
last_names AS (
    SELECT n, ROW_NUMBER() OVER (ORDER BY n) AS rn FROM (VALUES
    ('Abbott'),('Baker'),('Bell'),('Bennett'),('Black'),('Boyd'),('Brooks'),('Brown'),
    ('Burns'),('Butler'),('Campbell'),('Carter'),('Chapman'),('Clark'),('Cole'),('Collins'),
    ('Cook'),('Cooper'),('Crawford'),('Cunningham'),('Day'),('Dixon'),('Douglas'),('Drake'),
    ('Duncan'),('Edwards'),('Elliott'),('Ferguson'),('Ford'),('Foster'),('Fox'),('Freeman'),
    ('Gibson'),('Gonzalez'),('Gordon'),('Graham'),('Grant'),('Gray'),('Hamilton'),('Harper'),
    ('Harris'),('Hart'),('Hayes'),('Henderson'),('Holland'),('Holmes'),('Hunter'),('James')
    ) AS t(n)
),
numbered AS (
    SELECT
        f.n AS first_name,
        l.n AS last_name,
        ROW_NUMBER() OVER (ORDER BY f.rn, l.rn) AS seq
    FROM first_names f
    CROSS JOIN last_names l
)
INSERT INTO sales.customers (first_name, last_name, email, territory_id, customer_type, credit_limit, created_at)
SELECT TOP 470
    first_name,
    last_name,
    LOWER(first_name) + '.' + LOWER(last_name) + CAST(seq AS NVARCHAR(10)) + '@example.com',
    ((seq - 1) % 20) + 1,
    CASE WHEN seq % 3 = 0 THEN 'B2B' ELSE 'B2C' END,
    CASE WHEN seq % 3 = 0 THEN 10000.00 + (seq * 100) ELSE NULL END,
    DATEADD(DAY, (seq % 730), '2023-01-01')
FROM numbered
ORDER BY seq;
GO

-- 8.13  Sales: Promotions
SET IDENTITY_INSERT sales.promotions ON;
INSERT INTO sales.promotions (id, name, discount_percent, start_date, end_date, min_order_amount, is_active) VALUES
(1,  'New Year Sale',           15.0, '2025-01-01', '2025-01-15', 100.00,  0),
(2,  'Valentine Special',      10.0, '2025-02-10', '2025-02-16', 50.00,   0),
(3,  'Spring Clearance',       25.0, '2025-03-15', '2025-04-15', 200.00,  0),
(4,  'Summer Blowout',         20.0, '2025-06-01', '2025-06-30', 150.00,  0),
(5,  'Back to School',         15.0, '2025-08-01', '2025-09-01', 75.00,   0),
(6,  'Black Friday',           30.0, '2025-11-25', '2025-11-30', 100.00,  0),
(7,  'Cyber Monday',           25.0, '2025-12-01', '2025-12-02', 50.00,   0),
(8,  'Holiday Season',         20.0, '2025-12-10', '2025-12-31', 200.00,  0),
(9,  'New Year 2026',          15.0, '2026-01-01', '2026-01-15', 100.00,  0),
(10, 'Spring 2026',            20.0, '2026-03-15', '2026-04-15', 150.00,  1);
SET IDENTITY_INSERT sales.promotions OFF;
GO

-- 8.14  Sales: Orders (~3000) and Order Items (~8000)
-- Generate orders spanning 2024-01-01 to 2026-03-20

-- We use a numbers table approach to generate bulk data.
;WITH nums AS (
    SELECT TOP 3000 ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n
    FROM sys.objects a CROSS JOIN sys.objects b
),
order_data AS (
    SELECT
        n AS seq,
        -- Customer: cycle through 1-500
        ((n - 1) % 500) + 1 AS customer_id,
        -- Employee: sales reps (ids 44-51, 68, 80) cycling
        CASE (n % 10)
            WHEN 0 THEN 44 WHEN 1 THEN 45 WHEN 2 THEN 46 WHEN 3 THEN 47
            WHEN 4 THEN 48 WHEN 5 THEN 49 WHEN 6 THEN 50 WHEN 7 THEN 51
            WHEN 8 THEN 80 WHEN 9 THEN 44
        END AS employee_id,
        -- Order date: spread across 2024-01-01 to 2026-03-20 (~810 days)
        DATEADD(DAY, (n % 810), '2024-01-01') AS order_date,
        -- Status distribution
        CASE
            WHEN n % 100 < 5  THEN 'cancelled'
            WHEN n % 100 < 8  THEN 'returned'
            WHEN n % 100 < 12 THEN 'pending'
            WHEN n % 100 < 20 THEN 'confirmed'
            WHEN n % 100 < 40 THEN 'shipped'
            ELSE 'delivered'
        END AS status,
        -- Shipping cost
        ROUND(5.00 + (n % 30) * 1.50, 2) AS shipping_cost
    FROM nums
)
INSERT INTO sales.orders (customer_id, employee_id, order_date, required_date, shipped_date, status, shipping_cost)
SELECT
    customer_id,
    employee_id,
    order_date,
    DATEADD(DAY, 7, order_date),
    CASE
        WHEN status IN ('shipped', 'delivered') THEN DATEADD(DAY, 2 + (seq % 5), order_date)
        ELSE NULL
    END,
    status,
    shipping_cost
FROM order_data;
GO

-- Generate order items (2-4 items per order, ~8000 total)
;WITH order_ids AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS rn FROM sales.orders
),
item_counts AS (
    SELECT id, rn,
           2 + (rn % 3) AS num_items  -- 2, 3, or 4 items per order
    FROM order_ids
),
items_expanded AS (
    SELECT
        ic.id AS order_id,
        n.n AS item_num,
        -- Product: distribute across products 1-150
        ((ic.rn * 7 + n.n * 13) % 147) + 1 AS product_id,
        -- Quantity: 1-5
        1 + ((ic.rn + n.n) % 5) AS quantity,
        -- Discount: most get 0, some get 5-15%
        CASE WHEN (ic.rn + n.n) % 8 = 0 THEN 10.0
             WHEN (ic.rn + n.n) % 12 = 0 THEN 5.0
             WHEN (ic.rn + n.n) % 20 = 0 THEN 15.0
             ELSE 0.0
        END AS discount_percent
    FROM item_counts ic
    CROSS APPLY (
        SELECT TOP (ic.num_items) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n
        FROM sys.objects
    ) n
)
INSERT INTO sales.order_items (order_id, product_id, quantity, unit_price, discount_percent)
SELECT
    ie.order_id,
    ie.product_id,
    ie.quantity,
    p.unit_price,
    ie.discount_percent
FROM items_expanded ie
JOIN inventory.products p ON p.id = ie.product_id;
GO

-- 8.15  Sales: Order-Promotion mappings (apply promotions to orders that fall in promo date ranges)
INSERT INTO sales.order_promotions (order_id, promotion_id)
SELECT DISTINCT o.id, p.id
FROM sales.orders o
JOIN sales.promotions p ON o.order_date BETWEEN p.start_date AND p.end_date
WHERE o.status NOT IN ('cancelled', 'returned')
  AND o.id % 3 = 0;  -- ~1/3 of eligible orders get the promo
GO

-- 8.16  Finance: Invoices (one per non-cancelled order)
INSERT INTO finance.invoices (order_id, invoice_date, due_date, total_amount, tax_amount, status, paid_date)
SELECT
    o.id,
    o.order_date,
    DATEADD(DAY, 30, o.order_date),
    ISNULL(oi_totals.subtotal, 0) + o.shipping_cost,
    ROUND(ISNULL(oi_totals.subtotal, 0) * 0.08, 2),  -- 8% tax
    CASE
        WHEN o.status = 'cancelled' THEN 'void'
        WHEN o.status = 'delivered' AND o.order_date < DATEADD(DAY, -30, GETDATE()) THEN 'paid'
        WHEN o.order_date < DATEADD(DAY, -30, GETDATE()) THEN 'overdue'
        WHEN o.status IN ('shipped', 'delivered') THEN 'sent'
        ELSE 'draft'
    END,
    CASE
        WHEN o.status = 'delivered' AND o.order_date < DATEADD(DAY, -30, GETDATE())
        THEN DATEADD(DAY, 15 + (o.id % 20), o.order_date)
        ELSE NULL
    END
FROM sales.orders o
LEFT JOIN (
    SELECT order_id, SUM(quantity * unit_price * (1 - discount_percent / 100.0)) AS subtotal
    FROM sales.order_items
    GROUP BY order_id
) oi_totals ON oi_totals.order_id = o.id
WHERE o.status <> 'cancelled';
GO

-- 8.17  Finance: Payments (one payment per paid invoice, some split payments)
INSERT INTO finance.payments (invoice_id, payment_date, amount, payment_method, reference_number)
SELECT
    i.id,
    i.paid_date,
    i.total_amount + i.tax_amount,
    CASE (i.id % 5)
        WHEN 0 THEN 'credit_card'
        WHEN 1 THEN 'bank_transfer'
        WHEN 2 THEN 'credit_card'
        WHEN 3 THEN 'wire'
        WHEN 4 THEN 'paypal'
    END,
    'PAY-' + RIGHT('00000000' + CAST(i.id AS NVARCHAR(10)), 8)
FROM finance.invoices i
WHERE i.status = 'paid' AND i.paid_date IS NOT NULL;
GO

-- Add some split payments (second partial payment on ~5% of paid invoices)
INSERT INTO finance.payments (invoice_id, payment_date, amount, payment_method, reference_number)
SELECT TOP 150
    i.id,
    DATEADD(DAY, 5, i.paid_date),
    ROUND((i.total_amount + i.tax_amount) * 0.1, 2),  -- 10% additional/adjustment
    'bank_transfer',
    'PAY-ADJ-' + RIGHT('00000000' + CAST(i.id AS NVARCHAR(10)), 8)
FROM finance.invoices i
WHERE i.status = 'paid' AND i.paid_date IS NOT NULL AND i.id % 20 = 0
ORDER BY i.id;
GO

-- 8.18  Finance: Budget Allocations (for each department, 4 quarters of 2025 + Q1 2026)
INSERT INTO finance.budget_allocations (department_id, fiscal_year, fiscal_quarter, allocated_amount, spent_amount, category)
SELECT
    d.id,
    y.yr,
    q.qtr,
    ROUND(d.budget / 4.0 * (0.4 + ABS(CHECKSUM(NEWID())) % 100 / 200.0), 2),
    ROUND(d.budget / 4.0 * (0.3 + ABS(CHECKSUM(NEWID())) % 100 / 250.0), 2),
    c.cat
FROM hr.departments d
CROSS JOIN (VALUES (2025), (2026)) AS y(yr)
CROSS JOIN (VALUES (1), (2), (3), (4)) AS q(qtr)
CROSS JOIN (VALUES ('personnel'), ('operations'), ('technology')) AS c(cat)
WHERE (y.yr = 2025 OR (y.yr = 2026 AND q.qtr = 1));
GO

-- 8.19  Support: Tickets (~400)
;WITH ticket_data AS (
    SELECT TOP 400
        ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS seq
    FROM sys.objects a CROSS JOIN sys.objects b
)
INSERT INTO support.tickets (customer_id, assigned_employee_id, subject, description, priority, status, category, created_at, resolved_at, satisfaction_rating)
SELECT
    ((seq - 1) % 500) + 1,
    -- Support agents: 56-60, 79, 18
    CASE (seq % 7)
        WHEN 0 THEN 56 WHEN 1 THEN 57 WHEN 2 THEN 58
        WHEN 3 THEN 59 WHEN 4 THEN 60 WHEN 5 THEN 79 WHEN 6 THEN 18
    END,
    CASE (seq % 12)
        WHEN 0  THEN 'Order not received'
        WHEN 1  THEN 'Wrong item delivered'
        WHEN 2  THEN 'Billing discrepancy'
        WHEN 3  THEN 'Request for refund'
        WHEN 4  THEN 'Product malfunction'
        WHEN 5  THEN 'Account login issue'
        WHEN 6  THEN 'Shipping delay inquiry'
        WHEN 7  THEN 'Warranty claim'
        WHEN 8  THEN 'Price match request'
        WHEN 9  THEN 'Subscription cancellation'
        WHEN 10 THEN 'Missing order items'
        WHEN 11 THEN 'Damaged package'
    END,
    'Customer reported an issue requiring attention.',
    CASE (seq % 10)
        WHEN 0 THEN 'critical'
        WHEN 1 THEN 'high' WHEN 2 THEN 'high'
        WHEN 3 THEN 'medium' WHEN 4 THEN 'medium' WHEN 5 THEN 'medium' WHEN 6 THEN 'medium'
        WHEN 7 THEN 'low' WHEN 8 THEN 'low' WHEN 9 THEN 'low'
    END,
    CASE
        WHEN seq % 5 = 0 THEN 'open'
        WHEN seq % 5 = 1 THEN 'in_progress'
        WHEN seq % 5 = 2 THEN 'resolved'
        WHEN seq % 5 = 3 THEN 'closed'
        WHEN seq % 5 = 4 THEN 'waiting_customer'
    END,
    CASE (seq % 6)
        WHEN 0 THEN 'billing'
        WHEN 1 THEN 'shipping'
        WHEN 2 THEN 'product_defect'
        WHEN 3 THEN 'returns'
        WHEN 4 THEN 'account'
        WHEN 5 THEN 'general'
    END,
    DATEADD(DAY, -(seq % 365), GETUTCDATE()),
    CASE WHEN seq % 5 IN (2, 3)
         THEN DATEADD(HOUR, 4 + (seq % 72), DATEADD(DAY, -(seq % 365), GETUTCDATE()))
         ELSE NULL
    END,
    CASE WHEN seq % 5 IN (2, 3)
         THEN 1 + (seq % 5)
         ELSE NULL
    END
FROM ticket_data;
GO

-- 8.20  Support: Ticket Comments (~1000, 2-3 per resolved/closed ticket, 1 per others)
;WITH ticket_ids AS (
    SELECT id, status, ROW_NUMBER() OVER (ORDER BY id) AS rn
    FROM support.tickets
),
comment_data AS (
    -- First comment for every ticket
    SELECT id AS ticket_id, 1 AS comment_num, rn FROM ticket_ids
    UNION ALL
    -- Second comment for resolved/closed/in_progress tickets
    SELECT id, 2, rn FROM ticket_ids WHERE status IN ('resolved', 'closed', 'in_progress')
    UNION ALL
    -- Third comment for resolved/closed tickets
    SELECT id, 3, rn FROM ticket_ids WHERE status IN ('resolved', 'closed')
)
INSERT INTO support.ticket_comments (ticket_id, author_employee_id, comment_text, is_internal, created_at)
SELECT
    ticket_id,
    CASE (rn % 7)
        WHEN 0 THEN 56 WHEN 1 THEN 57 WHEN 2 THEN 58
        WHEN 3 THEN 59 WHEN 4 THEN 60 WHEN 5 THEN 79 WHEN 6 THEN 18
    END,
    CASE comment_num
        WHEN 1 THEN 'Initial review of the ticket. Gathering information from the customer.'
        WHEN 2 THEN 'Follow-up with customer completed. Working on resolution.'
        WHEN 3 THEN 'Issue has been resolved. Customer has been notified of the outcome.'
    END,
    CASE WHEN comment_num = 2 AND rn % 4 = 0 THEN 1 ELSE 0 END,
    DATEADD(HOUR, comment_num * 6, GETUTCDATE())
FROM comment_data;
GO

-- ============================================
-- 9. SUMMARY STATISTICS (verify counts)
-- ============================================
SELECT 'hr.departments'          AS [table], COUNT(*) AS [rows] FROM hr.departments          UNION ALL
SELECT 'hr.employees',                       COUNT(*)           FROM hr.employees             UNION ALL
SELECT 'hr.employee_addresses',              COUNT(*)           FROM hr.employee_addresses    UNION ALL
SELECT 'hr.salary_history',                  COUNT(*)           FROM hr.salary_history        UNION ALL
SELECT 'sales.regions',                      COUNT(*)           FROM sales.regions            UNION ALL
SELECT 'sales.territories',                  COUNT(*)           FROM sales.territories        UNION ALL
SELECT 'sales.customers',                    COUNT(*)           FROM sales.customers          UNION ALL
SELECT 'sales.orders',                       COUNT(*)           FROM sales.orders             UNION ALL
SELECT 'sales.order_items',                  COUNT(*)           FROM sales.order_items        UNION ALL
SELECT 'sales.promotions',                   COUNT(*)           FROM sales.promotions         UNION ALL
SELECT 'sales.order_promotions',             COUNT(*)           FROM sales.order_promotions   UNION ALL
SELECT 'inventory.categories',               COUNT(*)           FROM inventory.categories     UNION ALL
SELECT 'inventory.products',                 COUNT(*)           FROM inventory.products       UNION ALL
SELECT 'inventory.suppliers',                COUNT(*)           FROM inventory.suppliers       UNION ALL
SELECT 'inventory.product_suppliers',        COUNT(*)           FROM inventory.product_suppliers UNION ALL
SELECT 'inventory.warehouses',               COUNT(*)           FROM inventory.warehouses     UNION ALL
SELECT 'inventory.stock_levels',             COUNT(*)           FROM inventory.stock_levels   UNION ALL
SELECT 'finance.invoices',                   COUNT(*)           FROM finance.invoices         UNION ALL
SELECT 'finance.payments',                   COUNT(*)           FROM finance.payments         UNION ALL
SELECT 'finance.budget_allocations',         COUNT(*)           FROM finance.budget_allocations UNION ALL
SELECT 'support.tickets',                    COUNT(*)           FROM support.tickets          UNION ALL
SELECT 'support.ticket_comments',            COUNT(*)           FROM support.ticket_comments
ORDER BY [table];
GO
