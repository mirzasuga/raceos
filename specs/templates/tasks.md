# Task Breakdown: {{ title }}

## Summary

{{ summary }}

---

{% for task in tasks %}
## Task {{ loop.index }}: {{ task.title }}

**Domain:** {{ task.domain }}
**Files:** {{ task.files | join(', ') }}
**Complexity:** {{ task.complexity }}

### Description

{{ task.description }}

### Acceptance Criteria

{% for ac in task.acceptance_criteria %}
- [ ] {{ ac }}
{% endfor %}

---

{% endfor %}
