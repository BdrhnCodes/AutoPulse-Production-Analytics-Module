## Status
✅ Data pipeline (Python + SQL): complete
🔄 Power BI dashboard: in progress

# AutoPulse — Automotive Manufacturing Analytics (Jungle Motors)

End-to-end synthetic data engineering project simulating a car factory's
production line, from raw material intake to finished-vehicle quality
control. Built with Python (data generation + ML), SQL (SQLite), and
Power BI (dashboard).

## What this project does

- Simulates 2 years of production for a fictional automaker (Jungle Motors,
  4 models including one EV) across a 20-station assembly line
- Models realistic manufacturing dynamics: takt-time-balanced stations,
  worker skill effects, sequence-dependent paint changeover, and a
  multi-factor defect probability model tied to supplier reliability and
  part complexity
- Loads ~1.8M rows into a relational SQLite database (16 tables, 5
  reporting views)
- Runs SQL + pandas analysis: labor bottlenecks, cost breakdown, defect
  Pareto analysis, OEE, and a defect-risk ML model (Logistic Regression +
  Random Forest)
- Exports clean tables for a Power BI dashboard

## Tech stack
Python (pandas, NumPy, Faker, scikit-learn) · SQLite · SQL · Power BI

## Project structure

- config/ --> single source of truth for all parameters
- data_generation/ --> 8 scripts, run in order (see below)
- sql/ --> schema (01) + reporting views (02)
- database/ --> SQLite setup + data loading
- analysis/ --> SQL/pandas analysis + ML model
- export/ --> final CSV export for Power BI
- data/powerbi_export/ --> what Power BI actually connects to

## How to run it end to end
pip install -r requirements.txt

# 1) Dimensions + BOM
- python data_generation/generate_dimensions.py
- python data_generation/generate_bom.py

# 2) Production simulation
- python data_generation/generate_production_orders.py
- python data_generation/generate_production_units.py
- python data_generation/generate_station_operations.py
- python data_generation/generate_defects.py
- python data_generation/generate_material_usage.py
- python data_generation/finalize_production_units.py

# 3) Database
- python database/db_setup.py
- python database/load_to_db.py

# 4) Analysis
- python analysis/labor_time_analysis.py
- python analysis/cost_analysis.py
- python analysis/defect_analysis.py
- python analysis/oee_calculation.py
- python analysis/defect_risk_model.py

# 5) Power BI export
- python export/export_powerbi_views.py


Every script uses a fixed random seed (`config.yaml -> project.random_seed`),
so re-running the full pipeline reproduces identical results.

## Key design decisions

- **Synthetic data, deliberately**: real automotive production-line data
  (labor hours, station-level defect rates) is proprietary and never
  publicly released, a hand-built simulation with realistic, calibrated
  parameters is the only viable option for a portfolio project.
- **Defect rate calibration**: tuned against published First Pass Yield
  benchmarks (~90-96% for a typical automotive line) rather than picked
  arbitrarily.
- **Rolled Throughput Yield**: even a low per-station defect rate
  compounds across 20 stations , the ~92% overall pass rate is the
  expected mathematical consequence, not an inflated assumption.


## Author's note

I built this project after completing three certificates and a production internship:

- CS50's Introduction to Artificial Intelligence with Python (Harvard University)
- CS50's Introduction to Databases with SQL (Harvard University)
- Prepare and Visualize Data with Power BI (Microsoft)
- Production internship at an automotive parts factory

During my manufacturing internship, I observed the production line and took notes about
production processes. With those observations and my software background, I developed a
synthetic manufacturing simulation project that includes sequence-dependent paint 
changeovers (color-based, not random), takt-time-balanced station cycle times, and more.
