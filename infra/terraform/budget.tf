# Budget alert — notifica por email ao atingir 80% de USD 10/mês.

resource "azurerm_consumption_budget_resource_group" "main" {
  name              = "ai-professor-budget"
  resource_group_id = azurerm_resource_group.main.id

  amount     = 10
  time_grain = "Monthly"

  time_period {
    start_date = "2025-04-01T00:00:00Z"
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.budget_alert_email]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_emails = [var.budget_alert_email]
  }
}
