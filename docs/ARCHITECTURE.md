# Data Lineage Platform: Architecture and Lineage

GitHub draws the Mermaid diagrams in this file.

The platform is one FastAPI application hosting six applications. It follows the lineage sheet:
**DAO (SOO) → YXY (SOR) → AOC (APP) → MIS Report**. These match the three zones of the End-to-End Lineage diagram:
System of Origination, System of Record and Authorized Provisioning Point, and Data Consumers.

## 1. Platform overview

```mermaid
flowchart LR
  USER["User<br/>browser"] --> FE["Frontend<br/>HTML, CSS, JavaScript"]
  FE --> API["FastAPI<br/>app/main.py"]

  subgraph APPS["Six applications"]
    CAT["1. CDE Catalog<br/>/catalog"]
    DAO["2. DAO, SOO<br/>/dao"]
    YXY["3. YXY, SOR<br/>/yxy"]
    AOC["4. AOC, APP<br/>/aoc"]
    MIS["5. MIS Report<br/>/mis"]
    CTL["6. Controls<br/>/controls"]
  end

  API --> APPS
  DAO -->|"records"| YXY
  YXY -->|"records"| AOC
  AOC -->|"records"| MIS
  MIS --> CTL
  DB[("SQLite<br/>lineage.db")]
  APPS <--> DB
  CSV["CSV uploads<br/>DAO extract and account master"] --> DAO
  CSV --> YXY
  JSON["data/cde_lineage.json<br/>the lineage sheet"] --> CAT
  MIS --> XLS["MIS_14MQ.xlsx"]
```

## 2. What happens on Run full pipeline

```mermaid
sequenceDiagram
  autonumber
  actor User
  participant UI as Frontend
  participant API as main.py
  participant CAT as Catalog
  participant DAO as DAO
  participant YXY as YXY
  participant AOC as AOC
  participant MIS as MIS Report
  participant CTL as Controls
  participant DB as SQLite

  User->>UI: Run full pipeline
  UI->>API: POST /api/run-all
  API->>DB: clear previous results
  API->>CAT: run
  CAT->>DB: save lineage sheet and findings
  API->>DAO: run
  DAO->>DB: save source extract
  API->>YXY: run
  YXY->>DB: read DAO, save YXY and rejects
  API->>AOC: run
  AOC->>DB: read YXY, save AOC
  API->>MIS: run
  MIS->>DB: read AOC, save report
  API->>CTL: run
  CTL->>DB: read every layer, save control results
  API-->>UI: run summaries
  UI-->>User: counts, report, control results
```

## 3. What happens to a record

```mermaid
flowchart TD
  A["DAO record"] --> B{"Business group and file month<br/>match the parameters?"}
  B -->|"No"| F["Filtered out"]
  B -->|"Yes"| C{"Duplicate clrty_id?"}
  C -->|"Yes"| D["Duplicate removed"]
  C -->|"No"| E{"Amount present and not negative,<br/>PIF inputs present,<br/>account master row found?"}
  E -->|"No"| R["Rejected with a reason"]
  E -->|"Yes"| G["YXY: map columns,<br/>add account numbers and interest"]
  G --> H["AOC: rename columns"]
  H --> I["AOC: settlement_amount =<br/>outstanding_bal + interest_amount"]
  H --> J["AOC: PIF flag from<br/>active, charge-off, closure, balance"]
  I --> K["MIS Report row"]
  J --> K
  K --> L{"Controls C1 to C5"}
  L -->|"All pass"| M["Report verified"]
  L -->|"Any fail"| N["Break reported"]
```

## 4. Lineage of Settlement Amount

Field names are the physical names from the lineage sheet.

```mermaid
flowchart LR
  A1["DAO<br/>settlement_am"] --> A2["YXY<br/>outstanding_balance"]
  A2 --> A3["AOC<br/>outstanding_bal"]
  B1["YXY<br/>interest_amt"] --> B2["AOC<br/>interest_amount"]
  A3 -->|"input"| C["AOC<br/>settlement_amount"]
  B2 -->|"input"| C
  C --> D["MIS Report<br/>Settlement Amount"]
  A3 --> E["MIS Report<br/>Outstanding Balance"]
  B2 --> F["MIS Report<br/>Interest Amount"]
```

## 5. Lineage of PIF (Paid in Full)

```mermaid
flowchart LR
  S1["DAO and YXY<br/>account_gross_balance_am"] --> P
  S2["DAO and YXY<br/>charge_off_in"] --> P
  S3["DAO and YXY<br/>active_in"] --> P
  S4["DAO and YXY<br/>closure_reason_cd"] --> P
  P["AOC<br/>PIF<br/>derived flag"] --> M["MIS Report<br/>PIF"]
```

## 6. Field mapping across hops

| CDE | DAO (SOO) | YXY (SOR) | AOC (APP) | MIS Report | What happens |
|---|---|---|---|---|---|
| Treatment | `workout_completed_cd` | `treatment_cd` | `Treatment` | `Treatment` | Passed through, renamed |
| Outstanding Balance | `settlement_am` | `outstanding_balance` | `outstanding_bal` | `Outstanding Balance` | Passed through, renamed |
| Interest Amount | not documented | `interest_amt` | `interest_amount` | `Interest Amount` | Created at YXY |
| Settlement Amount | not documented | not documented | `settlement_amount` | `Settlement Amount` | Derived at AOC |
| Account Number | not documented | `account_nm` | `account_number` | `Account Number` | Created at YXY |
| Child_AccountNumber | not documented | `chld_account_nm` | `child_account_number` | `Child_AccountNumber` | Created at YXY |
| Ledger_AccountNumber | not documented | `ldgr_account_nm` | `ledger_account_number` | `Ledger_AccountNumber` | Created at YXY |
| PIF | sub-fields | sub-fields | `PIF` | `PIF` | Derived at AOC |

## 7. Controls

| Control | Check | Result type |
|---|---|---|
| C1 | DAO rows are fully accounted for at YXY, and YXY, AOC and MIS row counts agree | Fail on any break |
| C2 | Pass-through fields in the report equal the source values | Fail on any break |
| C3 | Settlement Amount recomputed from DAO and YXY equals the report | Fail on any break |
| C4 | PIF recomputed from the source sub-fields equals the report | Fail on any break |
| C5 | Every report column is documented at the MIS hop in the lineage sheet | Warning |

## 8. API surface

| Path | Purpose |
|---|---|
| `POST /api/run-all` | Reset and run all six apps. Optional: `inject_fault`, `file_month`, `business_group` |
| `POST /api/reset` | Clear pipeline results |
| `POST /api/reset-sources` | Go back to the built-in sample data and default parameters |
| `GET /api/status` | Last run summary per app, parameters and data sources |
| `GET /api/trace/{clrty_id}` | One record at every hop, with physical field names |
| `POST /{app}/run`, `GET /{app}/output` | Run or read each app: catalog, dao, yxy, aoc, mis, controls |
| `GET /dao/sample.csv`, `POST /dao/upload` | Download the sample DAO file, upload your own |
| `GET /yxy/account-master.csv`, `POST /yxy/upload-account-master` | Same for the account master |
| `GET /mis/download` | MIS_14MQ.xlsx with a Controls sheet |
| `GET /catalog/mermaid/{cde}` | Mermaid lineage for one CDE |
