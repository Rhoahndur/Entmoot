%% MVP+ Site Layouts - System Architecture Diagram
%% AI-Driven Site Layout Automation Platform

graph TB
    subgraph "User Interface Layer"
        UI[React Frontend Application]
        Upload[File Upload Wizard]
        Config[Configuration Panel]
        MapView[Interactive Map Viewer]
        Editor[Layout Editor]
        Dashboard[Results Dashboard]
        Export[Export Manager]
    end

    subgraph "API Gateway Layer"
        Gateway[FastAPI Gateway]
        Auth[Authentication & Authorization]
        RateLimit[Rate Limiter]
        Router[API Router]
    end

    subgraph "Core Processing Modules"
        Ingestion[Data Ingestion Module]
        Validation[File Validation & Parsing]
        TerrainEngine[Terrain Analysis Engine]
        ConstraintMgr[Constraint Management System]
        Optimizer[AI Placement Optimizer]
        RoadGen[Road Network Generator]
        CutFill[Cut/Fill Calculator]
        ReportGen[Report Generator]
    end

    subgraph "Optimization Engine"
        GA[Genetic Algorithm]
        ObjFunc[Multi-Objective Function]
        Collision[Collision Detection]
        Constraints[Constraint Validator]
        Scorer[Layout Scoring Engine]
    end

    subgraph "Geospatial Processing"
        DEM[DEM Processor]
        Slope[Slope Calculator]
        Aspect[Aspect Analyzer]
        Buffer[Buffer Generator]
        Pathfinder[A* Pathfinding]
        Volume[Volume Calculator]
    end

    subgraph "Visualization Engine"
        Map2D[2D Map Renderer]
        Map3D[3D Terrain Viewer]
        PDFGen[PDF Report Generator]
        KMZGen[KMZ Exporter]
        GeoJSONGen[GeoJSON Exporter]
        DXFGen[DXF Exporter]
    end

    subgraph "External API Integrations"
        FEMA[FEMA Floodplain API]
        USGS[USGS Elevation API]
        Regulatory[Regulatory Database APIs]
        Weather[Weather/Climate APIs]
    end

    subgraph "Data Storage Layer"
        PostGIS[(PostGIS Database)]
        S3[S3 Object Storage]
        Redis[(Redis Cache)]
        FileStore[Temporary File Storage]
    end

    subgraph "Infrastructure & DevOps"
        Docker[Docker Containers]
        CI[GitHub Actions CI/CD]
        Monitoring[Prometheus + Grafana]
        Logging[ELK Stack]
        Sentry[Sentry Error Tracking]
    end

    %% User Interface Connections
    UI --> Upload
    UI --> Config
    UI --> MapView
    UI --> Editor
    UI --> Dashboard
    UI --> Export

    %% Frontend to Gateway
    Upload -.HTTP/REST.-> Gateway
    Config -.HTTP/REST.-> Gateway
    Editor -.HTTP/REST.-> Gateway
    Export -.HTTP/REST.-> Gateway

    %% Gateway Processing
    Gateway --> Auth
    Gateway --> RateLimit
    Gateway --> Router

    %% Router to Core Modules
    Router --> Ingestion
    Router --> TerrainEngine
    Router --> ConstraintMgr
    Router --> Optimizer
    Router --> RoadGen
    Router --> CutFill
    Router --> ReportGen

    %% Data Ingestion Flow
    Ingestion --> Validation
    Validation --> FileStore
    Validation --> PostGIS

    %% Terrain Analysis Flow
    TerrainEngine --> DEM
    TerrainEngine --> Slope
    TerrainEngine --> Aspect
    DEM --> Volume
    Slope --> PostGIS
    Aspect --> PostGIS

    %% Constraint Management Flow
    ConstraintMgr --> Buffer
    ConstraintMgr --> FEMA
    ConstraintMgr --> Regulatory
    FEMA -.API Call.-> Redis
    Regulatory -.API Call.-> Redis
    Buffer --> PostGIS

    %% Optimization Flow
    Optimizer --> GA
    Optimizer --> ObjFunc
    Optimizer --> Collision
    Optimizer --> Constraints
    GA --> Scorer
    ObjFunc --> Scorer
    Collision --> Constraints
    Scorer --> PostGIS

    %% Road Generation Flow
    RoadGen --> Pathfinder
    Pathfinder --> PostGIS

    %% Cut/Fill Flow
    CutFill --> Volume
    Volume --> PostGIS

    %% Visualization Flow
    ReportGen --> Map2D
    ReportGen --> Map3D
    ReportGen --> PDFGen
    ReportGen --> KMZGen
    ReportGen --> GeoJSONGen
    ReportGen --> DXFGen
    PDFGen --> S3
    KMZGen --> S3
    GeoJSONGen --> S3
    DXFGen --> S3

    %% External Data Sources
    USGS -.Elevation Data.-> TerrainEngine
    Weather -.Climate Data.-> Optimizer

    %% Data Storage Connections
    PostGIS -.Spatial Queries.-> TerrainEngine
    PostGIS -.Spatial Queries.-> ConstraintMgr
    PostGIS -.Spatial Queries.-> Optimizer
    PostGIS -.Spatial Queries.-> RoadGen
    PostGIS -.Spatial Queries.-> ReportGen
    S3 -.File Upload/Download.-> Ingestion
    S3 -.File Download.-> Export
    Redis -.Cache Hit/Miss.-> ConstraintMgr

    %% Monitoring & Logging
    Gateway --> Logging
    Optimizer --> Logging
    ReportGen --> Logging
    Gateway --> Monitoring
    Optimizer --> Monitoring
    Gateway --> Sentry
    Optimizer --> Sentry

    %% Deployment
    Docker -.Contains.-> Gateway
    Docker -.Contains.-> Optimizer
    Docker -.Contains.-> ReportGen
    CI -.Deploys.-> Docker

    %% Styling
    classDef frontend fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef backend fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef storage fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef external fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef infra fill:#fce4ec,stroke:#880e4f,stroke-width:2px

    class UI,Upload,Config,MapView,Editor,Dashboard,Export frontend
    class Gateway,Auth,RateLimit,Router,Ingestion,Validation,TerrainEngine,ConstraintMgr,Optimizer,RoadGen,CutFill,ReportGen,GA,ObjFunc,Collision,Constraints,Scorer,DEM,Slope,Aspect,Buffer,Pathfinder,Volume,Map2D,Map3D,PDFGen,KMZGen,GeoJSONGen,DXFGen backend
    class PostGIS,S3,Redis,FileStore storage
    class FEMA,USGS,Regulatory,Weather external
    class Docker,CI,Monitoring,Logging,Sentry infra
