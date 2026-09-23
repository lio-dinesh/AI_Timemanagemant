# AI Time Management System - Detailed System Architecture & Flow Diagrams

This document details the multi-tier system architecture, component lifecycles, and sequence flow diagrams of the **AI Time Management Platform (AI TimeSync)**.

---

## 1. High-Level Multi-Tier Infrastructure Architecture

The platform follows a layered, decoupled service architecture designed for high scalability, fault tolerance, concurrency safety, and responsive user interaction.

```mermaid
flowchart TB
    subgraph Client_Layer["Client Tier (Browser)"]
        UI["Bootstrap 5 + Vanilla CSS Modern UI"]
        HTMX["HTMX Dynamic Partials"]
        TimerJS["timer.js (Live Sync & Idle Detection)"]
        ChartJS["Chart.js Analytics Dashboards"]
        NLPBar["AI Command Bar (#nlp-input)"]
    end

    subgraph Ingress_Layer["Ingress & Edge Tier"]
        NGINX["Nginx / Cloud Reverse Proxy"]
        WhiteNoise["WhiteNoise Static Asset Server"]
        CSRF["Security & CSRF / SSL Termination"]
    end

    subgraph Application_Layer["Application Tier (Django 5.1 WSGI / ASGI)"]
        Auth["apps.accounts (RBAC: Admin / Manager / Employee)"]
        TasksApp["apps.tasks (Task Lifecycle & Rollups)"]
        TrackingApp["apps.tracking (TimerService & Concurrency Lock)"]
        SchedApp["apps.scheduling (Calendar & Conflict Detector)"]
        NotifApp["apps.notifications (NotificationEngine)"]
        AnalyticsApp["apps.analytics (Productivity Daily Rollups)"]
        AuditApp["apps.audit (Sanitized Audit Logging)"]
        
        subgraph AI_Engine["apps.ai (Intelligence Subsystem)"]
            Router["CommandRouter (Fast-Path <25ms)"]
            Parser["NLPParser (Hybrid Regex + Gemini)"]
            Resolver["EntityResolver (User / Task / Project)"]
            Executor["NLPExecutor & ToolRegistry"]
            Optimizer["ScheduleOptimizer (Knapsack / Priority)"]
            Anomaly["ProductivityAnomalyDetector (ML Outlier)"]
        end
    end

    subgraph Storage_Layer["Data & Persistence Tier"]
        MySQL[("MySQL 8.x InnoDB<br/>Source of Truth<br/>(Row-level select_for_update)")]
        Redis[("Redis 5.0+ / LocMemCache<br/>Session Store & Broker")]
    end

    subgraph Worker_Layer["Asynchronous Worker Tier (Celery 5.3)"]
        Worker["Celery Distributed Workers"]
        Beat["Celery Beat Scheduler (Periodic Tasks)"]
    end

    subgraph External_Cloud["External Cloud Integrations"]
        GeminiAPI["Google Gemini 3.6 Flash REST API"]
        BrevoAPI["Brevo SMTP Relay & REST API"]
        Recipient["User Email: liodinesh1905@gmail.com"]
    end

    %% Client to Ingress
    UI --> NGINX
    HTMX --> NGINX
    TimerJS --> NGINX
    NLPBar --> NGINX

    %% Ingress to App
    NGINX --> WhiteNoise
    NGINX --> CSRF --> Application_Layer

    %% App to Data & Workers
    Application_Layer --> MySQL
    Application_Layer --> Redis
    Application_Layer -.-> Worker

    %% Beat to Workers
    Beat --> Redis --> Worker

    %% AI Integrations
    Parser -.->|"LLM Completion"| GeminiAPI
    
    %% Notifications
    Worker -.->|"Transactional SMTP"| BrevoAPI
    BrevoAPI -.->|"Inbound Email"| Recipient
```

---

## 2. Core Subsystem Flow Diagrams

### Diagram 1: Natural Language Processing (NLP) Dual-Tier Command Flow

The NLP engine supports both instant deterministic actions (<25ms) and deep generative AI extraction powered by **Google Gemini 3.6 Flash**.

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Client
    participant UI as Command Bar (HTMX)
    participant Router as CommandRouter
    participant FastPath as Fast-Path Regex Engine
    participant Parser as NLPParser
    participant Gemini as Google Gemini 3.6 Flash
    participant Resolver as EntityResolver
    participant Executor as NLPExecutor
    participant DB as MySQL Database
    participant Notif as NotificationEngine

    User->>UI: Types: "create task Review Code by tomorrow 5pm assign to Dinesh"
    UI->>Router: POST /ai/nlp/execute/ (query, context)
    
    Router->>FastPath: Match deterministic commands (timer, show, help)?
    alt Deterministic Fast Path Match
        FastPath-->>Router: Fast Action (Duration <25ms)
    else Complex Intent (Requires Extraction)
        Router->>Parser: parse_with_gemini(query)
        Parser->>Gemini: POST /v1beta/models/gemini-3.6-flash:generateContent
        Note over Gemini: Extracts Title, Due Date, Priority (P1-P10), Assignee
        Gemini-->>Parser: Structured JSON Payload
        Parser-->>Router: ParsedIntent(TASK_CREATE, confidence: 0.98)
    end

    Router->>Resolver: resolve_user("Dinesh") & resolve_project()
    Resolver->>DB: Query User by email/username/fuzzy name
    DB-->>Resolver: User ID 1 (liodinesh1905@gmail.com)
    Resolver-->>Router: Resolved Entities

    Router->>Executor: execute_intent(intent, resolved_entities)
    Executor->>DB: INSERT INTO tasks (title, deadline, priority, assigned_to_id)
    DB-->>Executor: Task #8 Created
    
    Executor->>Notif: notify_task_assigned(task, actor)
    Note over Notif: Triggers In-App Notification & Celery Email Task
    
    Executor-->>UI: JSON Response (Success, Task Card, New Status)
    UI-->>User: Displays High-Contrast Confirmation Card
```

---

### Diagram 2: Real-Time Timer & Concurrency-Safe Tracking Flow

To prevent race conditions, time tracking uses atomic `select_for_update` database row locks and an automated rollover mechanism.

```mermaid
sequenceDiagram
    autonumber
    actor User as User
    participant Browser as timer.js
    participant View as TimerView (/tracking/timer/)
    participant Service as TimerService
    participant DB as MySQL (InnoDB)

    User->>Browser: Clicks "Start Timer" for Task #5
    Browser->>View: POST /tracking/timer/start/ {task_id: 5}
    View->>Service: start_timer(user, task)
    
    critical Database Transaction with Concurrency Lock
        Service->>DB: SELECT * FROM tracking_timeentry WHERE user_id=1 AND end_time IS NULL FOR UPDATE
        alt Active Timer Already Running for Another Task
            Service->>DB: UPDATE tracking_timeentry SET end_time=NOW() WHERE id=previous_entry.id
            Service->>DB: UPDATE tasks_task SET actual_seconds = actual_seconds + duration
        end
        Service->>DB: INSERT INTO tracking_timeentry (user_id, task_id, start_time, is_billable) VALUES (1, 5, NOW(), true)
    end

    DB-->>Service: New TimeEntry #42 created
    Service-->>View: Active Timer State
    View-->>Browser: HTTP 200 {status: "RUNNING", entry_id: 42, start_time: "..."}
    
    loop Every 1000ms (Client Live Counter)
        Browser->>Browser: Update elapsed display (HH:MM:SS)
    end

    loop Every 60s (Heartbeat Sync & Idle Detection)
        Browser->>View: POST /tracking/timer/ping/
        View->>Service: ping_heartbeat(entry_id)
        Service->>DB: UPDATE tracking_timeentry SET last_heartbeat=NOW()
    end
```

---

### Diagram 3: Proactive Notification & Brevo Email Lifecycle

The notification engine handles real-time alerts and dispatches transactional emails with asynchronous queue offloading.

```mermaid
sequenceDiagram
    autonumber
    actor Event as System / User Action (Create, Complete, Deadline)
    participant Engine as NotificationEngine
    participant DB as MySQL Database
    participant Celery as Celery Task Queue
    participant Worker as Celery Worker
    participant Brevo as Brevo SMTP Relay / API
    actor User as User (liodinesh1905@gmail.com)

    Event->>Engine: trigger_event(type, recipient, task)
    
    %% In-App Notification
    Engine->>DB: INSERT INTO notifications_notification (user_id, type, title, message, is_read)
    DB-->>Engine: Notification #17 stored
    
    %% Async Email Offload
    alt Recipient has email_enabled == True
        Engine->>Celery: send_brevo_email.delay(recipient_email, subject, html_content)
        Note over Celery: Non-blocking offload (Worker takes over)
    end

    Worker->>Celery: Poll & consume send_brevo_email task
    Worker->>Brevo: POST /v3/smtp/email (Rendered HTML with Priority Badges)
    Brevo-->>Worker: HTTP 201 Created (Message-ID: <20260923...>)
    Brevo->>User: Delivers Email to inbox
    
    opt Brevo Webhook Delivery Confirmation
        Brevo->>Engine: POST /notifications/webhook/brevo/ {event: "delivered", message_id: "..."}
        Engine->>DB: UPDATE notifications_notification SET delivery_status='DELIVERED'
    end
```

---

### Diagram 4: Periodic Deadline & Anomaly Analytics Flow

Automated Celery Beat workers ensure scheduled jobs run reliably without blocking web requests.

```mermaid
sequenceDiagram
    autonumber
    participant Beat as Celery Beat Scheduler
    participant Redis as Redis Queue
    participant Worker as Celery Worker
    participant TasksService as Deadline Scanner
    participant AnalyticsService as Productivity Service
    participant AnomalyDetector as ML Anomaly Engine
    participant DB as MySQL Database
    participant Brevo as Brevo Email Service

    Note over Beat: Every 15 minutes
    Beat->>Redis: Enqueue `check_deadlines` task
    Redis->>Worker: Dispatch task
    Worker->>TasksService: Scan tasks with deadline <= NOW() + 24h AND status != COMPLETED
    TasksService->>DB: Fetch approaching & overdue tasks
    TasksService->>Brevo: Dispatch deadline alert emails to assignees

    Note over Beat: Daily at 23:59:00
    Beat->>Redis: Enqueue `calculate_daily_productivity` & `run_periodic_anomaly_detection`
    Redis->>Worker: Dispatch analytics tasks
    Worker->>AnalyticsService: Aggregate TimeEntries, Completed Tasks, and Idle Time
    AnalyticsService->>DB: INSERT / UPDATE INTO analytics_productivitydaily (score, date, user_id)
    
    Worker->>AnomalyDetector: Run Isolation Forest / Z-Score on user history
    opt Outlier Detected (Productivity Drop / Extreme Overwork)
        AnomalyDetector->>DB: INSERT INTO ai_aiinsight (type="ANOMALY", confidence, recommendation)
    end
```

---

## 3. Database Entity Relationship (ER) Model

```mermaid
erDiagram
    CUSTOM_USER ||--o{ PROJECT : "creates / manages"
    CUSTOM_USER ||--o{ TASK : "assigned_to"
    CUSTOM_USER ||--o{ TIME_ENTRY : "records"
    CUSTOM_USER ||--o{ SCHEDULE_EVENT : "attends"
    CUSTOM_USER ||--o{ NOTIFICATION : "receives"
    CUSTOM_USER ||--o{ PRODUCTIVITY_DAILY : "evaluated_in"
    CUSTOM_USER ||--o{ AI_INSIGHT : "receives"
    CUSTOM_USER ||--o{ AUDIT_LOG : "triggers"

    PROJECT ||--o{ TASK : "contains"
    TASK ||--o{ TIME_ENTRY : "accumulates"
    TASK ||--o{ SCHEDULE_EVENT : "linked_to"

    CUSTOM_USER {
        int id PK
        string username
        string email "liodinesh1905@gmail.com"
        string role "ADMIN | MANAGER | EMPLOYEE"
        boolean email_enabled
        boolean is_active
        datetime date_joined
    }

    PROJECT {
        int id PK
        string name
        string client
        decimal budget_hours
        string status "ACTIVE | ARCHIVED | COMPLETED"
        int owner_id FK
    }

    TASK {
        int id PK
        string title
        text description
        string priority "P1 - P10"
        string status "TODO | IN_PROGRESS | REVIEW | COMPLETED"
        datetime deadline
        int estimated_seconds
        int actual_seconds "Cached rollup"
        int project_id FK
        int assigned_to_id FK
    }

    TIME_ENTRY {
        int id PK
        datetime start_time
        datetime end_time
        int duration_seconds
        boolean is_billable
        string source "MANUAL | TIMER | NLP"
        int task_id FK
        int user_id FK
    }

    SCHEDULE_EVENT {
        int id PK
        string title
        datetime start_datetime
        datetime end_datetime
        boolean is_ai_generated
        int task_id FK
        int user_id FK
    }

    NOTIFICATION {
        int id PK
        string notification_type "TASK_ASSIGNED | TASK_COMPLETED | DEADLINE"
        string title
        text message
        boolean is_read
        string delivery_status "PENDING | SENT | DELIVERED | FAILED"
        int user_id FK
    }

    PRODUCTIVITY_DAILY {
        int id PK
        date date
        decimal productivity_score "0.0 - 100.0"
        int completed_tasks_count
        int total_seconds_tracked
        int user_id FK
    }

    AI_INSIGHT {
        int id PK
        string insight_type "OPTIMIZATION | ANOMALY | FORECAST"
        text content
        decimal confidence
        boolean is_applied
        int user_id FK
    }

    AUDIT_LOG {
        int id PK
        string action "CREATE | UPDATE | DELETE | LOGIN"
        string resource_type
        int resource_id
        text changes_sanitized
        string ip_address
        int user_id FK
    }
```
