{% extends "base.html" %}
{% block title %}Stock Report{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <h4>Stock Report</h4>
  <a href="{{ url_for('reports.stock_report', low_stock=1 if low_only else 0, export='xlsx') }}" class="btn btn-success"><i class="bi bi-file-earmark-excel"></i> Export Excel</a>
</div>
<form class="row g-2 mb-3" method="get">
  <div class="col-auto form-check mt-2">
    <input class="form-check-input" type="checkbox" name="low_stock" value="1" id="lowstock" {% if low_only %}checked{% endif %}>
    <label class="form-check-label" for="lowstock">Low stock only</label>
  </div>
  <div class="col-auto"><button class="btn btn-outline-secondary">Filter</button></div>
</form>
<div class="card p-3 mb-3"><div class="text-muted small">Total Stock Value (at cost)</div><h4>{{ total_stock_value|money }}</h4></div>
<div class="card p-3">
<table class="table table-sm">
  <thead><tr><th>Code</th><th>Name</th><th>Category</th><th>Brand</th><th>Cost</th><th>Price</th><th>Stock</th><th>Reorder</th><th>Stock Value</th></tr></thead>
  <tbody>
  {% for r in rows %}
    <tr class="{{ 'table-danger' if r.stock_qty <= r.reorder_level else '' }}">
      <td>{{ r.item_code }}</td><td>{{ r.name }}</td><td>{{ r.category_name or '-' }}</td><td>{{ r.brand or '-' }}</td>
      <td>{{ r.cost_price|money }}</td><td>{{ r.selling_price|money }}</td><td>{{ r.stock_qty }} {{ r.unit }}</td>
      <td>{{ r.reorder_level }}</td><td>{{ r.stock_value|money }}</td>
    </tr>
  {% else %}
    <tr><td colspan="9" class="text-muted">No items.</td></tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% endblock %}
