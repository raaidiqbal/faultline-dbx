# Faultline incident console

The Databricks App in `app/` is a read-only Streamlit incident console. Its
bundle resource is `faultline_console`.

Authorization is resource-based:

- the app service principal receives `CAN_USE` on the existing serverless SQL
  warehouse through the `sql-warehouse` binding;
- it receives `SELECT` on only the four pipeline tables it queries;
- table names and the warehouse ID arrive through `valueFrom` environment
  variables; and
- runtime OAuth comes from the app's injected service-principal environment.

Never add a PAT, OAuth secret, workspace URL, or fixed table name to app code.
The bundle's warehouse lookup keeps the public configuration portable.

The console deliberately labels the active source as Lakebase-CDF-compatible
Delta. Do not change that to native Lakebase CDF until a workspace run proves
the source table was produced by the preview feature.

The app is authenticated inside the Databricks workspace. The resume-facing
artifact must therefore remain the public GitHub repository plus a short
recording or GIF, not the app URL itself.
