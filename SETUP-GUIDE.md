# n8n-MCP Setup Guide

Servidor MCP que dá ao Claude acesso completo à documentação de 1.650 nodes do n8n, templates e validação de workflows.

**Repositório:** https://github.com/czlonkowski/n8n-mcp

---

## Pré-requisitos

- [Node.js](https://nodejs.org/) instalado (v18+)
- Claude Desktop instalado

## Instalação (npx — sem instalar nada)

O npx baixa e roda automaticamente. Não precisa instalar globalmente.

Para testar manualmente no terminal:

```bash
npx n8n-mcp
```

## Configuração no Claude Desktop

### 1. Abra o arquivo de configuração

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

Caminho completo:
```
C:\Users\Daniel Ramos\AppData\Roaming\Claude\claude_desktop_config.json
```

### 2. Adicione (ou merge) o bloco do n8n-mcp

Se o arquivo **não existe**, crie-o com este conteúdo:

```json
{
  "mcpServers": {
    "n8n-mcp": {
      "command": "npx",
      "args": ["n8n-mcp"],
      "env": {
        "MCP_MODE": "stdio",
        "LOG_LEVEL": "error",
        "DISABLE_CONSOLE_OUTPUT": "true"
      }
    }
  }
}
```

Se o arquivo **já existe** com outros MCP servers, adicione o bloco `"n8n-mcp": {...}` dentro de `"mcpServers"`.

> ⚠️ **IMPORTANTE:** A variável `MCP_MODE: "stdio"` é obrigatória. Sem ela, você verá erros de JSON parsing no Claude Desktop.

### 3. Reinicie o Claude Desktop

Feche completamente e reabra. Pronto!

## Configuração com instância n8n (opcional)

Se você tiver uma instância n8n rodando, use esta config expandida:

```json
{
  "mcpServers": {
    "n8n-mcp": {
      "command": "npx",
      "args": ["n8n-mcp"],
      "env": {
        "MCP_MODE": "stdio",
        "LOG_LEVEL": "error",
        "DISABLE_CONSOLE_OUTPUT": "true",
        "N8N_API_URL": "https://sua-instancia-n8n.com",
        "N8N_API_KEY": "sua-api-key-aqui"
      }
    }
  }
}
```

Para n8n local: use `http://localhost:5678` como URL.

## O que você ganha

### Sem instância n8n (só documentação):
- Buscar e consultar 1.650 nodes (820 core + 830 community)
- Acessar 2.352 templates de workflows
- Validar configurações de nodes e workflows
- Ver exemplos reais de configuração

### Com instância n8n (gestão completa):
- Tudo acima, mais:
- Criar, editar e executar workflows
- Gerenciar workflows existentes
- Testar execuções

## Ferramentas disponíveis (MCP tools)

- `search_nodes` — buscar nodes por nome/função
- `get_node` — detalhes completos de um node
- `search_templates` — buscar templates de workflows
- `get_template` — obter template completo
- `validate_node` — validar configuração de node
- `validate_workflow` — validar workflow completo
- `tools_documentation` — guia de melhores práticas
- `n8n_create_workflow` — criar workflow (requer API)
- `n8n_update_partial_workflow` — atualizar workflow (requer API)
- `n8n_test_workflow` — testar workflow (requer API)

## Referências

- [Repositório n8n-MCP](https://github.com/czlonkowski/n8n-mcp)
- [Guia de Self-Hosting](https://github.com/czlonkowski/n8n-mcp/blob/main/docs/SELF_HOSTING.md)
- [Guia de Deploy n8n](https://github.com/czlonkowski/n8n-mcp/blob/main/docs/N8N_DEPLOYMENT.md)
- [n8n Skills (opcional)](https://github.com/czlonkowski/n8n-skills)
