# BigQuery Optimization

Performance and efficiency guidelines for BigQuery SQL queries.

## SQL Optimization Rules

> [!TIP]
> Always include a **"Summary of Optimizations"** section listing only the optimizations applied.

### Always Apply (Automatic)

| Optimization | Description |
| --- | --- |
| **Column Pruning** | Remove unnecessary columns from all query stages. |
| **Common Subexpression Reuse** | Factor out identical expressions to avoid redundant computation. |
| **Predicate Pushdown** | Apply `WHERE` filters as early as possible. |
| **Early Aggregation** | Perform `GROUP BY` before joins when possible. |
| **Intermediate Materialization** | Choose `VIEW` vs `TABLE` for intermediate nodes based on freshness, cost, and project-convention decisions. |

#### Intermediate Node Strategy

| Strategy | When to Use |
| --- | --- |
| **`VIEW`** | Small datasets, simple transformations, or when real-time freshness is required. |
| **`TABLE`** | Large datasets, expensive computations, or nodes reused multiple times where caching is beneficial. |

*Materialization Decision Guidelines:*
- Do not automatically change materialization based solely on reference count.
- Treat materialization changes as freshness, cost, and project-convention decisions.
- Gather validation evidence such as `EXPLAIN` plans, BigQuery dry-run/job metrics, and existing Dataform/dbt conventions.
- Obtain explicit user confirmation when a rewrite changes materialization or output semantics.

### Always Rewrite (Mandatory)

| Pattern | Replace With |
| --- | --- |
| `WHERE <col> IN (SELECT ...)` | `WHERE EXISTS (SELECT 1 FROM ...)` |
| `WHERE (SELECT COUNT(*) ...) > 0` | `WHERE EXISTS (SELECT 1 FROM ...)` |

### Propose with Confirmation (Conditional)

- **`UNION` → `UNION ALL`**: Faster (skips deduplication), but permits duplicate rows.
- **`COUNT(DISTINCT)` → `APPROX_COUNT_DISTINCT`**: Faster and lower memory, but approximate.
