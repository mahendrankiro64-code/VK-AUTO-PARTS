{% extends "base.html" %}
{% block title %}Day-End History Report{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <h4>Day-End History Report</h4>
  <a href="{{ url_for('reports.dayend_history_report', export='xlsx') }}" class="btn btn-success"><i class="bi bi-file-earmark-excel"></i> Export Excel</a>
</div>
<div class="card p-3">
<table class="table table-sm">
  <thead><tr><th>Date</th><th>Opening</th><th>Cash</th><th>Credit</th><th>Online</th><th>Expected</th><th>Actual</th><th>Status</th></tr></thead>
  <tbody>
  {% for r in rows %}
    <tr>
      <td>{{ r.business_date }}</td><td>{{ r.opening_balance|money }}</td><td>{{ r.cash_sales|money }}</td>
      <td>{{ r.credit_sales|money }}</td><td>{{ r.online_sales|money }}</td>
      <td>{{ r.closing_balance_expected|money }}</td>
      <td>{{ r.closing_balance_actual|money if r.closing_balance_actual is not none else '-' }}</td>
      <td>{{ r.status }}</td>
    </tr>
  {% else %}
    <tr><td colspan="8" class="text-muted">No records.</td></tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% endblock %}
