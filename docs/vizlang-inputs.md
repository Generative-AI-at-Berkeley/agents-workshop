# VizLang Input Examples

Open any `vizlang/mN.py` file in VizLang, paste the corresponding JSON below.

---

## Module 1 — Single Agent

```json
{
  "request": {
    "city": "San Francisco",
    "vibe": "tech house, underground",
    "date": "this saturday",
    "group_size": 4,
    "notes": ""
  },
  "messages": [],
  "itinerary": null
}
```

---

## Module 2 — Directed Graph + Conditional Edges

```json
{
  "request": {
    "city": "Berlin",
    "vibe": "techno, dark minimal",
    "date": "this saturday",
    "group_size": 6,
    "notes": ""
  },
  "messages": [],
  "plan": "",
  "raw_research": "",
  "itinerary": null,
  "review_passed": false,
  "review_feedback": "",
  "attempts": 0
}
```

---

## Module 3 — Tools (Firecrawl) + RBAC

Same shape as M2. Scout will use Firecrawl tools if `FIRECRAWL_API_KEY` is set.

```json
{
  "request": {
    "city": "Tokyo",
    "vibe": "jazz bars, speakeasy",
    "date": "friday night",
    "group_size": 2,
    "notes": "budget friendly, no cover charges"
  },
  "messages": [],
  "plan": "",
  "raw_research": "",
  "itinerary": null,
  "review_passed": false,
  "review_feedback": "",
  "attempts": 0
}
```

---

## Module 4 — Subagents

```json
{
  "request": {
    "city": "Los Angeles",
    "vibe": "house music, rooftop bars",
    "date": "this saturday",
    "group_size": 5,
    "notes": "someone in the group doesn't drink"
  },
  "messages": [],
  "plan": "",
  "scout_assignments": [],
  "raw_research": "",
  "itinerary": null,
  "review_passed": false,
  "review_feedback": "",
  "attempts": 0
}
```

---

## Module 5 — Parallel Fan-Out + Merge

```json
{
  "request": {
    "city": "New York",
    "vibe": "warehouse rave, afterhours",
    "date": "this saturday",
    "group_size": 8,
    "notes": "at least one stop in Brooklyn"
  },
  "messages": [],
  "plan": "",
  "scout_assignments": [],
  "raw_research": "",
  "merged_research": "",
  "itinerary": null,
  "review_passed": false,
  "review_feedback": "",
  "attempts": 0
}
```

---

## API Examples (curl)

```bash
# Module 1
curl -s -X POST http://localhost:8200/runs \
  -H "Content-Type: application/json" \
  -d '{"city":"San Francisco","vibe":"tech house","date":"this saturday","group_size":4,"module":1}'

# Module 2
curl -s -X POST http://localhost:8200/runs \
  -H "Content-Type: application/json" \
  -d '{"city":"Berlin","vibe":"techno, dark minimal","date":"this saturday","group_size":6,"module":2}'

# Module 4
curl -s -X POST http://localhost:8200/runs \
  -H "Content-Type: application/json" \
  -d '{"city":"Los Angeles","vibe":"house music, rooftop bars","date":"this saturday","group_size":5,"module":4}'

# Module 5
curl -s -X POST http://localhost:8200/runs \
  -H "Content-Type: application/json" \
  -d '{"city":"New York","vibe":"warehouse rave, afterhours","date":"this saturday","group_size":8,"module":5}'

# Check a run result
curl -s http://localhost:8200/runs/<run_id> | python3 -m json.tool
```
