# Cursor-Based Pagination Implementation

This document describes the enhanced pagination system that supports both traditional offset-based pagination and efficient cursor-based pagination.

## Overview

The standard pagination system now automatically detects and uses the most appropriate pagination method:

- **Cursor-based pagination**: For frequently updated datasets (reports, audit logs)
- **Offset-based pagination**: For stable datasets (search results, user lists)

## Backend Implementation

### New Functions in `app/lib/standard_pagination.py`

#### `generate_pagination_cursors(items, *, cursor_field, page_size, total_available=None)`
Generates cursor values for pagination from a list of database items.

```python
# Example usage
reports = await query_reports()
cursors = generate_pagination_cursors(reports, cursor_field='id', page_size=20)
# Returns: [100, 80, 60, 40, 20] (first item ID of each page)
```

#### `cursor_pagination_params(cursor, *, direction='after', page_size=20, cursor_field='id')`
Generates parameters for cursor-based database queries.

```python
# Example usage  
params = cursor_pagination_params(cursor=90, page_size=10)
# Returns: {'limit': 10, 'id': 90, 'direction': 'after'}
```

### Database Query Pattern

For cursor-based queries, use this pattern:

```python
async def find_items_cursor(*, after=None, before=None, limit=20):
    conditions = []
    params = []
    
    if after is not None:
        conditions.append(SQL('id > %s'))
        params.append(after)
    
    if before is not None:
        conditions.append(SQL('id < %s'))
        params.append(before)

    query = SQL("""
        SELECT * FROM table_name
        WHERE {}
        ORDER BY updated_at DESC, id DESC
        LIMIT %s
    """).format(SQL(' AND ').join(conditions) if conditions else SQL('TRUE'))
    
    params.append(limit)
    # Execute query...
```

## Frontend Implementation

### Template Usage

Templates can provide both pagination modes:

```jinja2
<ul class="pagination"
    data-action="/api/web/reports/cursors?status={{ status }}"
    data-cursors="{{ cursors | tojson if cursors else '[]' }}"
    data-pages="{{ total_pages }}"
    data-fallback-action="/api/web/reports?page={page}&status={{ status }}">
</ul>
```

### JavaScript API

The `configureStandardPagination()` function automatically detects the pagination mode:

```typescript
// Automatically uses cursor-based pagination if cursors are available
const dispose = configureStandardPagination(container);
```

## Controller Implementation

### Enhanced Report Controller Example

```python
@router.get('/reports')
async def reports_index(status: str = ''):
    # Get cursors and count in parallel
    async with TaskGroup() as tg:
        cursors_task = tg.create_task(ReportQuery.generate_report_cursors(open=open))
        count_task = tg.create_task(ReportQuery.count_all(open=open))

    cursors = await cursors_task
    total_items = await count_task
    
    return await render_response('reports/index', {
        'cursors': cursors,
        'reports_num_items': total_items,
        'reports_num_pages': ceil(total_items / PAGE_SIZE),
    })

@router.get('/reports/cursors')  
async def reports_page_cursors(after: int = None, before: int = None):
    reports = await ReportQuery.find_reports_cursor(after=after, before=before)
    # Process and return results...
```

## Benefits

### Cursor-Based Pagination Advantages
- **Consistent results**: No duplicate/missing items when data changes during pagination
- **Better performance**: Uses indexed columns instead of OFFSET
- **Real-time safe**: Works correctly with frequently updated data

### When to Use Each Method
- **Use cursor-based**: Reports, audit logs, activity feeds, comments
- **Use offset-based**: Search results, user directories, static lists

## Testing

Comprehensive tests are included in `tests/lib/test_standard_pagination.py`:

```bash
# Run pagination tests
python -m pytest tests/lib/test_standard_pagination.py -v
```

## Migration Guide

Existing offset-based pagination continues to work unchanged. To add cursor support:

1. Add cursor query methods to your Query class
2. Update your controller to generate cursors
3. Update your template to include cursor data attributes
4. The frontend automatically uses cursors when available

No breaking changes are required for existing implementations.