# {{ title }}

## Problem Statement

{{ problem }}

## Scope

{{ scope }}

## Success Criteria

{% for criterion in criteria %}
- [ ] {{ criterion }}
{% endfor %}

## Out of Scope

{% for item in out_of_scope %}
- {{ item }}
{% endfor %}

## Estimated Complexity

{{ complexity }}

## Constraints (from Brain)

{% for constraint in constraints %}
- {{ constraint }}
{% endfor %}
