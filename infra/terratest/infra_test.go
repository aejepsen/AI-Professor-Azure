// =============================================================================
// Terratest — AI Professor v1
// Provisiona infra real, valida recursos criados corretamente, depois destroi.
// Rodar UMA vez para certificar a infra. CI/CD usa apenas plan + validate.
//
// Uso:
//   cd infra/terratest
//   go test -v -timeout 30m -run TestAIProfessorInfra
// =============================================================================

package test

import (
	"fmt"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestAIProfessorInfra(t *testing.T) {
	t.Parallel()

	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: "../terraform",
		VarFiles:     []string{"../terraform/prod.tfvars"},
		// Sem -target: testa tudo que o plan provisiona
	})

	// Garantir destroy ao final — mesmo se o teste falhar
	defer terraform.Destroy(t, terraformOptions)

	// Apply
	terraform.InitAndApply(t, terraformOptions)

	// -------------------------------------------------------------------------
	// 1. Resource Group deve existir
	// -------------------------------------------------------------------------
	resourceGroupName := terraform.Output(t, terraformOptions, "resource_group_name")
	assert.Equal(t, "ai-professor-prod-rg", resourceGroupName,
		"Resource Group deve ter o nome correto")

	// -------------------------------------------------------------------------
	// 2. Container App deve ter URL pública acessível
	// -------------------------------------------------------------------------
	containerAppURL := terraform.Output(t, terraformOptions, "container_app_url")
	require.NotEmpty(t, containerAppURL, "Container App URL não pode ser vazia")
	assert.True(t, strings.HasPrefix(containerAppURL, "https://"),
		"Container App URL deve usar HTTPS")

	// Aguarda o Container App inicializar (cold start pode demorar)
	healthURL := fmt.Sprintf("%s/health", containerAppURL)
	assertHTTPEventuallyReturns200(t, healthURL, 3*time.Minute)

	// -------------------------------------------------------------------------
	// 3. Static Web App deve estar provisionado com URL válida
	// -------------------------------------------------------------------------
	staticWebAppURL := terraform.Output(t, terraformOptions, "static_web_app_url")
	require.NotEmpty(t, staticWebAppURL, "Static Web App URL não pode ser vazia")
	assert.True(t, strings.HasPrefix(staticWebAppURL, "https://"),
		"Static Web App URL deve usar HTTPS")

	// Static Web App token de deploy deve existir (necessário para CI/CD)
	staticWebAppToken := terraform.OutputForKeys(t, terraformOptions, []string{"static_web_app_api_key"})
	require.NotEmpty(t, staticWebAppToken["static_web_app_api_key"],
		"Static Web App API key deve ser gerada pelo Terraform")

	// -------------------------------------------------------------------------
	// 4. App Registrations devem ter Client IDs válidos
	// -------------------------------------------------------------------------
	apiClientID := terraform.Output(t, terraformOptions, "api_app_registration_client_id")
	frontendClientID := terraform.Output(t, terraformOptions, "frontend_app_registration_client_id")

	assert.NotEmpty(t, apiClientID, "App Registration da API deve ter Client ID")
	assert.NotEmpty(t, frontendClientID, "App Registration do Frontend deve ter Client ID")
	assert.NotEqual(t, apiClientID, frontendClientID,
		"App Registrations da API e Frontend devem ter Client IDs diferentes")

	// -------------------------------------------------------------------------
	// 5. Endpoint /health deve retornar status ok (valida secrets injetados)
	// -------------------------------------------------------------------------
	resp, err := http.Get(healthURL)
	require.NoError(t, err, "GET /health não deve retornar erro de rede")
	defer resp.Body.Close()
	assert.Equal(t, 200, resp.StatusCode,
		"/health deve retornar 200 — confirma que o container subiu com os secrets corretos")

	// -------------------------------------------------------------------------
	// 6. Endpoint sem token deve retornar 401/403 (auth ativa em produção)
	// -------------------------------------------------------------------------
	chatURL := fmt.Sprintf("%s/chat/stream", containerAppURL)
	respUnauth, err := http.Post(chatURL, "application/json",
		strings.NewReader(`{"query":"test"}`))
	require.NoError(t, err)
	defer respUnauth.Body.Close()
	assert.True(t,
		respUnauth.StatusCode == 401 || respUnauth.StatusCode == 403,
		"/chat/stream sem token deve retornar 401 ou 403, não %d", respUnauth.StatusCode)
}

// assertHTTPEventuallyReturns200 tenta GET até o timeout, esperando 200.
// Necessário para cold start do Container App (scale-to-zero).
func assertHTTPEventuallyReturns200(t *testing.T, url string, timeout time.Duration) {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		resp, err := http.Get(url)
		if err == nil && resp.StatusCode == 200 {
			resp.Body.Close()
			return
		}
		if resp != nil {
			resp.Body.Close()
		}
		time.Sleep(10 * time.Second)
	}
	t.Fatalf("GET %s não retornou 200 após %v", url, timeout)
}
