# Decision Log — Monday.com BI Agent

## Key Assumptions

1. **Board Structure**: Assumed that the Work Orders and Deals boards have column names containing recognizable keywords (e.g., "value", "sector", "status", "date"). The agent dynamically maps columns by keyword matching rather than hardcoding specific column IDs, making it resilient to different board configurations.

2. **Currency Format**: Assumed Indian Rupee (₹) as the primary currency given the Skylark Drones context. Currency parsing handles ₹, $, €, £ symbols and Indian number formatting (lakhs/crores).

3. **Data Volume**: Assumed boards have fewer than ~5,000 items. The pagination implementation handles larger boards, but the data context sent to the LLM is optimized for boards in this range to stay within token limits.

4. **Read-Only Access**: The agent only reads data from Monday.com. No write operations are performed, as specified in the requirements.

## Trade-offs

### Google Gemini over OpenAI
- **Chose**: Gemini 2.0 Flash (free tier, generous rate limits)
- **Trade-off**: Slightly less capable than GPT-4 for complex analytical reasoning, but provides zero-cost operation for a prototype. The data context approach (structured summaries + raw samples) compensates by pre-computing aggregations.
- **With more time**: Would add provider abstraction to support multiple LLMs.

### Full Data Context vs. Tool-Use Pattern
- **Chose**: Send pre-computed data summaries and samples to the LLM in every request
- **Trade-off**: Uses more tokens per request but avoids multi-step tool-calling latency. For boards under 5K items, the token cost is negligible on free tier.
- **With more time**: Would implement function-calling where the LLM requests specific analyses (e.g., "filter deals by sector=Energy") rather than receiving all data upfront.

### FastAPI + Vanilla Frontend over Full Framework
- **Chose**: FastAPI backend + plain HTML/CSS/JS frontend
- **Trade-off**: No component framework (React/Vue), but the chat UI is simple enough that vanilla JS keeps the project lightweight, fast to deploy, and dependency-minimal.
- **With more time**: Would use React/Next.js for richer interactions (charts, filters, drill-downs).

### TTL Cache over Real-Time Sync
- **Chose**: 5-minute in-memory cache for Monday.com data
- **Trade-off**: Data could be up to 5 minutes stale. Users can manually refresh via the UI button.
- **With more time**: Would implement Monday.com webhooks for real-time data sync, or at minimum reduce TTL with smarter invalidation.

## Interpretation: "Leadership Updates"

Interpreted as: **Generate a structured executive summary report** suitable for founder/C-suite review.

The report includes:
- **Pipeline Overview**: Total deals, pipeline value, deal stage distribution
- **Sector Analysis**: Deal count and revenue by industry vertical
- **Operational Summary**: Work order counts, status breakdown, top clients
- **Data Quality Flags**: Highlights missing or incomplete data
- **Key Takeaways**: Auto-generated actionable insights

The report is accessible via a dedicated button in the UI and can be downloaded as a Markdown file. This approach was chosen because leadership updates are typically periodic (weekly/monthly) rather than ad-hoc, and a structured report format is more actionable than raw data or conversational answers.

## What I'd Do Differently With More Time

1. **Visualization**: Add charts (Chart.js/D3) for pipeline funnels, revenue trends, sector comparisons
2. **Streaming Responses**: Implement SSE streaming for real-time LLM output instead of waiting for full response
3. **Memory & Sessions**: Persistent conversation history with session management for multi-user support
4. **Advanced Analytics**: Time-series analysis, forecasting, anomaly detection on deal pipeline
5. **Testing**: Comprehensive unit tests for data processing, integration tests with mock Monday.com API
6. **Authentication**: Add user auth for the hosted version (currently open access for prototype)
7. **Export Formats**: PDF report generation in addition to Markdown
