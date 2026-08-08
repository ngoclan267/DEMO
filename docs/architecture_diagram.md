# Kien truc he thong (chuan SMCC: Listen -> Analyze -> Respond -> Report)

```mermaid
flowchart TD
    subgraph LISTEN["LISTEN"]
        A[Nguon du lieu that\nGoogle Play / App Store / LinkedIn] --> B[Collector Agent]
        B --> C[(Database)]
    end

    subgraph ANALYZE["ANALYZE"]
        C --> D[Processing Agent]
        D --> E[Classification Agent]
        E --> F[Verification Agent]
        F --> G[Consensus Agent]
        G --> H[Pain Point Agent]
    end

    subgraph RESPOND["RESPOND"]
        H --> I[Notification Service]
        H --> P["PATCH /pain-points/{id}\nTrang thai / nguoi phu trach / ghi chu xu ly"]
    end

    subgraph REPORT["REPORT"]
        I --> J[Dashboard theo chu de]
        I --> K[Email]
        P --> R["GET /report/summary\nKPI / SLA / so sanh cross-brand"]
    end

    R -.chu ky moi.-> B
```

Chu ky Listen->Analyze: 15-30 phut/lan (near real-time) - xem PRD muc 10.
Respond/Report la lop nghiep vu con nguoi thao tac tren ket qua pipeline
(khong phai mot Agent), xem PRD muc 10 va `src/api/routes.py`.

## LangGraph state graph

`src/agents/graph.py` bien luong tren thanh mot `StateGraph` voi state schema
dinh nghia trong `src/agents/state.py`. Moi node tuong ung mot agent, nhan va
tra ve mot phan cua `AgentState`.
