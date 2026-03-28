// src/environments/environment.prod.ts
export const environment = {
  production:  true,
  apiUrl:      '',   // Injetado pelo CI via ANGULAR_ENV_API_URL
  clientId:    '',   // Injetado pelo CI via ANGULAR_ENV_CLIENT_ID
  tenantId:    '',   // Injetado pelo CI via ANGULAR_ENV_TENANT_ID
  apiScope:    '',   // Injetado pelo CI via ANGULAR_ENV_API_SCOPE
  teamsTabUrl: '',
};
