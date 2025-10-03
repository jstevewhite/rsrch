# Using Serper-API-MCP for Web Search

## Recommendation: ✅ Use the MCP Tool

Your existing **serper-api-mcp** tool is the **perfect choice** for this project. Here's why:

## Advantages

### 1. **Intent-Aware Search**
The MCP tool provides three specialized search endpoints that align perfectly with your pipeline's intent classification:

- `search`: General web search (for INFORMATIONAL, CODE, TUTORIAL, GENERAL intents)
- `search_news`: News-specific search (for NEWS intent)
- `search_scholar`: Academic/scholarly search (for RESEARCH intent)

### 2. **Already Configured**
```json
"serper-api-mcp": {
  "command": "node",
  "args": ["/Volumes/SAM2/CODE/MCP/serper-api-mcp/serper-api-mcp/build/index.js"],
  "env": {
    "SERPER_API_KEY": "e48bfa72dee2189550a0468ee4eb9a985939e8dd"
  }
}
```
You have everything ready - no additional setup needed!

### 3. **MCP Protocol Benefits**
- Standardized interface
- Error handling built-in
- Consistent with Warp's architecture
- Easy to test and debug
- Automatic retries (likely)

### 4. **Maintenance**
- Updates handled upstream
- Community support
- Bug fixes automatically available
- No custom code to maintain

## Comparison: MCP Tool vs Direct API

| Feature | Serper MCP Tool | Direct Serper API |
|---------|----------------|-------------------|
| Setup time | ✅ 0 minutes (done) | ❌ 30-60 minutes |
| Error handling | ✅ Built-in | ❌ Implement yourself |
| Rate limiting | ✅ Handled | ❌ Implement yourself |
| Multiple search types | ✅ 3 tools ready | ❌ Write separate code |
| Testing | ✅ Use Warp's MCP tools | ⚠️ Write custom tests |
| Maintenance | ✅ Upstream updates | ❌ Your responsibility |
| Code complexity | ✅ Simple tool calls | ❌ HTTP client + parsing |

## Implementation Example

### Basic Usage in `researcher.py`:

```python
from call_mcp_tool import call_mcp_tool

# Select tool based on intent
def _select_search_tool(intent: Intent) -> str:
    if intent == Intent.NEWS:
        return "search_news"
    elif intent == Intent.RESEARCH:
        return "search_scholar"
    else:
        return "search"

# Execute search
search_tool = _select_search_tool(plan.query.intent)
results = call_mcp_tool(
    name=search_tool,
    input={
        "query": "your search query",
        "num_results": 10,
        "country_code": "us",
        "language": "en"
    }
)
```

### Response Format
The serper-api-mcp returns search results with:
- `title`: Page title
- `link`: URL
- `snippet`: Description/preview text
- `position`: Result ranking

These map directly to your `SearchResult` model:
```python
SearchResult(
    url=result['link'],
    title=result['title'],
    snippet=result['snippet'],
    rank=result['position']
)
```

## When Would Direct API Be Better?

Direct API calls would only make sense if:
- ❌ You need features not exposed by the MCP tool
- ❌ You need very custom error handling
- ❌ You're not using Warp/MCP at all
- ❌ The MCP tool has bugs or limitations

**None of these apply to your project!**

## Next Steps

1. ✅ Use the MCP tool (recommended)
2. Implement `stages/researcher.py` with MCP tool calls
3. Test with different intent types:
   - NEWS: Should use `search_news`
   - RESEARCH: Should use `search_scholar`
   - CODE: Should use `search`
4. Handle results and pass to scraper stage

## Testing the MCP Tool

You can test the serper-api-mcp directly in Warp before implementing:

```bash
# Test general search
warp mcp call serper-api-mcp search '{"query": "Python asyncio", "num_results": 5}'

# Test news search
warp mcp call serper-api-mcp search_news '{"query": "AI latest news", "num_results": 5}'

# Test scholar search
warp mcp call serper-api-mcp search_scholar '{"query": "transformer attention", "num_results": 5}'
```

## Conclusion

**Use the serper-api-mcp tool.** It's:
- Already configured
- Intent-aware
- Well-maintained
- MCP-native
- Easier to implement
- More maintainable

There's no compelling reason to call the Serper API directly when you have a perfectly good MCP tool ready to use!
