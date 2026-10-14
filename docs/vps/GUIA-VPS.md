# Guia: monitorar a VPS real com o SMI

Este guia liga a VPS (Ubuntu, Hostinger KVM 2) ao SMI que roda no seu PC. A ligação é feita pela rede privada do **Tailscale**. São dois jeitos de coletar, e dá para usar os dois ao mesmo tempo:

| | Agente (principal) | SNMP (opcional) |
| --- | --- | --- |
| Quem inicia | a VPS **envia** a cada 15 s | o PC **consulta** a cada 15 s |
| O que roda na VPS | `smi-agent` (Python, ~20 MB) | `snmpd` (serviço padrão do Linux, ~10 MB) |
| Se o PC estiver desligado | guarda as leituras e reenvia depois (até ~24 h) | nada é coletado no período |
| Queda da VPS detectada por | ausência de envio (watchdog no backend) | falta de resposta à consulta |

## O que este guia **não** mexe na VPS

nginx/Apache, PHP, Laravel, banco de dados, firewall e os sites ficam como estão. Os dois serviços instalados aqui só **leem** métricas do sistema. O agente roda com limites rígidos aplicados pelo próprio Linux: no máximo **5% de uma CPU** e **128 MB** de memória, com prioridade mínima, usuário temporário sem privilégios e sistema de arquivos somente leitura. Mesmo com defeito, ele não consegue disputar recursos com os sites. A seção 10 mostra como desfazer tudo.

> **Métricas da VPS:** CPU, memória, disco, uptime e disponibilidade. **Temperatura não existe** numa VPS, porque a máquina é virtual e não enxerga os sensores do hardware da Hostinger. O painel mostra isso como "indisponível". Os servidores simulados continuam demonstrando os gatilhos de temperatura.

---

## 1. No PC: token forte e API aceitando conexões do Tailscale

1. Gere um token aleatório (na pasta `backend`):
   ```powershell
   .venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. Crie ou edite `backend\.env` (modelo em `backend\.env.example`) e coloque:
   ```
   SMI_INGEST_TOKEN=<o token gerado>
   ```
   Reinicie a API e o coletor simulado (ele lê o token do mesmo `.env`).
3. A API passa a ser iniciada com `--host 0.0.0.0`, para aceitar conexões vindas do Tailscale:
   ```powershell
   .venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0
   ```
   Se o Windows perguntar se quer liberar o Python no firewall, clique em **Cancelar**. A liberação certa, só para o Tailscale, é feita no passo 5.

## 2. Tailscale no PC

1. Baixe e instale: https://tailscale.com/download/windows
2. Faça login. Use uma conta Google ou GitHub **com verificação em duas etapas ativada**, porque quem controla essa conta controla a rede.
3. Anote o IP do PC no Tailscale. Ele começa com `100.` e aparece clicando no ícone da bandeja, ou com:
   ```powershell
   tailscale ip -4
   ```

## 3. Tailscale na VPS

Acesse a VPS por SSH como de costume e rode:

```bash
curl -fsSL https://tailscale.com/install.sh | sh     # instalador oficial
sudo tailscale up                                   # abre um link: faça login com a MESMA conta do PC
tailscale ip -4                                     # anote o IP da VPS (100.x.y.z)
```

Não use `--ssh`, `--advertise-exit-node` nem `--advertise-routes`: o SMI não precisa deles.

**Teste:** no PC, `ping <IP da VPS no Tailscale>` deve responder.

## 4. Restringir a rede (política de acesso)

Por padrão, aparelhos da mesma rede Tailscale se enxergam por completo. A política em [`tailscale-acl.json`](tailscale-acl.json) libera **só** o que o SMI usa.

1. No painel do Tailscale (https://login.tailscale.com/admin/machines), marque as máquinas com **Edit ACL tags**: o PC com `tag:smi-pc` e a VPS com `tag:smi-vps`.
2. Em **Access controls**, substitua o conteúdo pelo de `tailscale-acl.json` e salve.

Bônus: aparelhos com tag não têm a chave de acesso expirando, então a VPS não cai da rede depois de 180 dias.

## 5. Firewall do Windows: liberar a API só para o Tailscale

No PowerShell **como administrador**:

```powershell
New-NetFirewallRule -DisplayName "SMI API (somente Tailscale)" -Direction Inbound -Protocol TCP -LocalPort 8000 -RemoteAddress 100.64.0.0/10 -Action Allow -Profile Any
```

`100.64.0.0/10` é a faixa de IPs do Tailscale. A rede de casa e a internet continuam sem acesso à porta 8000.

**Teste**, na VPS:

```bash
curl http://<IP do PC no Tailscale>:8000/api/v1/health
```

Deve responder `{"status":"ok", ...}`.

## 6. Cadastrar a VPS no painel

No painel, vá em **Servidores → Cadastrar servidor**:

- **Identificador:** `vps-nome`. É ele que vai no `SMI_HOST_ID` do agente.
- **Endereço:** o IP da VPS no Tailscale.
- **Forma de coleta:** Agente.

O servidor aparece como **Real** e fica em "Sem dados" até o agente começar a enviar.

## 7. Instalar o agente na VPS

1. Copie a pasta do agente do PC para a VPS. No PowerShell do PC, na pasta do projeto, use o **IP público** da VPS, o mesmo do seu SSH de sempre (está no painel da Hostinger):
   ```powershell
   scp -r backend\agent <usuario>@<IP PÚBLICO da VPS>:/tmp/smi-agent
   ```
   Se o seu SSH usa outra porta, acrescente `-P <porta>`. **Não use o IP do Tailscale (100.x.y.z) aqui:** a política do passo 4 bloqueia a porta 22 dentro da rede Tailscale, de propósito, e a conexão dá *timeout*.
2. Na VPS, instale. O script mostra o que faz e **não inicia nada sozinho**:
   ```bash
   cd /tmp/smi-agent
   sudo bash install.sh
   ```
   No fim ele mostra uma leitura de teste, por exemplo `{"cpu": 3.1, "ram": 41.2, "disk": 22.0, ...}`, sem enviar nada.
3. Configure:
   ```bash
   sudo nano /etc/smi-agent/agent.env
   ```
   ```
   SMI_API_URL=http://<IP do PC no Tailscale>:8000/api/v1
   SMI_INGEST_TOKEN=<o mesmo token do backend\.env>
   SMI_HOST_ID=<nome que definiu no sistema de monitoramento>
   SMI_INTERVAL=15
   ```
4. Inicie e acompanhe:
   ```bash
   sudo systemctl enable --now smi-agent
   journalctl -u smi-agent -f          # deve aparecer "conectado à API"  (Ctrl+C para sair)
   ```
5. Confira o consumo real (útil para a seção 4.5 do TCC):
   ```bash
   systemctl status smi-agent          # linhas "Memory:" e "CPU:"
   ```

## 8. Conferir no painel e testar a detecção de queda

- Em **Servidores → vps-hostinger**, os valores de CPU, memória e disco aparecem em até 15 s, com o selo **Real**.
- **Teste de queda**, para medir o tempo de detecção (TCC 4.5):
  ```bash
  sudo systemctl stop smi-agent      # simula a VPS caindo
  ```
  Em cerca de 80 s o alerta crítico **"Host inalcançável"** aparece. Depois:
  ```bash
  sudo systemctl start smi-agent     # o alerta resolve sozinho cerca de 45 s depois
  ```
- **PC desligado:** o agente guarda as leituras e as envia quando a API volta, sem gerar alerta falso.

## 9. (Opcional) Coleta por SNMP

Demonstra o protocolo central da monografia (seção 2.3.1) na mesma VPS. O mais didático é cadastrar uma **segunda entrada** para a VPS, coletada por SNMP. Assim o painel mostra lado a lado o modelo de envio (agente) e o de consulta (SNMP).

1. Na VPS, instale o `snmpd` e aplique a configuração do SMI (somente leitura, só pela rede Tailscale, só SNMPv3):
   ```bash
   sudo apt-get install -y snmpd
   sudo systemctl stop snmpd
   sudo cp /etc/snmp/snmpd.conf /etc/snmp/snmpd.conf.original      # backup
   ```
   Copie os arquivos do PC para a VPS, de novo pelo **IP público**, na pasta do projeto:
   ```powershell
   scp backend\collector\snmpd.conf backend\collector\snmpd-override.conf <usuario>@<IP PÚBLICO da VPS>:/tmp/
   ```
   E na VPS, colando **uma linha por vez** (colar várias linhas juntas no terminal SSH pode embaralhar os comandos):
   ```bash
   cd /tmp
   sudo cp snmpd.conf /etc/snmp/snmpd.conf
   IP=$(tailscale ip -4)
   sudo sed -i "s/TAILSCALE_IP_DA_VPS/$IP/" /etc/snmp/snmpd.conf
   grep agentaddress /etc/snmp/snmpd.conf      # deve mostrar udp:100.x.y.z:161
   ```
2. Crie o usuário SNMPv3, **com o `snmpd` parado**. Ao desligar, o snmpd regrava esse arquivo e descartaria uma linha adicionada com ele ligado. Escolha duas senhas com **8 ou mais caracteres**, as mesmas que vão no cadastro do painel:
   ```bash
   echo 'createUser smi SHA "SENHA-DE-AUTENTICACAO" AES "SENHA-DE-CRIPTOGRAFIA"' | sudo tee -a /var/lib/snmp/snmpd.conf
   ```
   Ao iniciar, o `snmpd` converte essa linha numa chave e apaga as senhas em texto puro do arquivo.
3. Faça o `snmpd` esperar o Tailscale no boot e inicie:
   ```bash
   sudo mkdir -p /etc/systemd/system/snmpd.service.d
   sudo cp snmpd-override.conf /etc/systemd/system/snmpd.service.d/smi.conf
   sudo systemctl daemon-reload
   sudo systemctl enable --now snmpd
   ss -ulpn | grep 161     # deve mostrar o snmpd escutando SÓ no IP 100.x.y.z
   ```
4. No painel, **Cadastrar servidor**:
   - **Identificador:** `vps-<provedor-nome>-snmp`
   - **Endereço:** o IP da VPS no Tailscale
   - **Coleta:** SNMP v3, usuário `smi` e as duas senhas
5. No PC, teste uma consulta (pasta `backend`):
   ```powershell
   .venv\Scripts\python -m collector.snmp_poller --test vps-<provedor-nome>-snmp
   ```
   Deve aparecer algo como `vps-<provedor-nome>-snmp (120 ms): reachable=1, cpu=..., ram=..., disk=...`.
6. Deixe o coletor rodando num terminal à parte:
   ```powershell
   .venv\Scripts\python -m collector.snmp_poller
   ```

## 10. Desfazer tudo

Agente, na VPS:

```bash
cd /tmp/smi-agent && sudo bash uninstall.sh
```

SNMP, na VPS:

```bash
sudo systemctl disable --now snmpd
sudo rm -rf /etc/systemd/system/snmpd.service.d/smi.conf && sudo systemctl daemon-reload
sudo apt-get purge -y snmpd            # remove o pacote e a configuração
```

Tailscale, na VPS: `sudo tailscale down`, e para remover, `sudo apt-get purge -y tailscale`.

No PC, a regra de firewall:

```powershell
Remove-NetFirewallRule -DisplayName "SMI API (somente Tailscale)"
```

E no painel: **Servidores → vps-hostinger → Remover**.

## Problemas comuns

| Sintoma | Causa provável |
| --- | --- |
| `journalctl` mostra "API inacessível" | PC desligado, API sem `--host 0.0.0.0`, regra de firewall faltando ou Tailscale desconectado em uma das pontas. Teste com o `curl` do passo 5. |
| "token recusado pela API" | O `SMI_INGEST_TOKEN` do `agent.env` é diferente do `backend\.env`, ou a API não foi reiniciada depois de mudar o `.env`. |
| "servidor 'x' não cadastrado" | O `SMI_HOST_ID` não bate com o identificador cadastrado no painel. |
| "servidor ... é simulado" | A entrada no painel está em modo **Simulado**. Use **Passar para real**. |
| "collected_at está no futuro" | Relógio da VPS ou do PC errado. Na VPS: `timedatectl` deve mostrar `System clock synchronized: yes`. |
| SNMP: "No SNMP response received before timeout" | `snmpd` parado, IP errado no `agentaddress`, ACL do Tailscale sem a porta 161, ou usuário/senhas diferentes das cadastradas. |
| SNMP: "Ciphering services not available" | Falta o pacote `cryptography` no PC: `.venv\Scripts\pip install -r requirements.txt`. |
