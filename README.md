# 🐸 SAPA - Sistema de Automação de Presença Acadêmica

O **SAPA** é um projeto de extensão acadêmica desenvolvido para solucionar um problema real na rotina do curso de Análise e Desenvolvimento de Sistemas (ADS) da UNISEPE: a ineficiência e a perda de tempo com as chamadas manuais de papel.

O sistema automatiza o controle de frequência e permanência dos alunos em sala de aula através da integração direta com leitores de código de barras USB, utilizando as carteirinhas físicas da própria instituição.

## 🚀 Funcionalidades Principais

* **Leitura Rápida e Automação:** Registro instantâneo de entrada e saída via código de barras.
* **Trava de Duplicidade (Regra de Negócio):** Sistema de segurança que impede bips duplicados do mesmo RA em um intervalo inferior a 5 minutos, garantindo a integridade dos dados.
* **Arquitetura Offline-First:** O sistema continua funcionando perfeitamente em sala de aula mesmo sem internet, armazenando os bips localmente.
* **Sincronização em Nuvem:** Quando há conexão, os dados locais são sincronizados de forma assíncrona com o banco na nuvem.
* **Relatórios e Analytics:** Exportação do histórico completo de presenças em Excel para alimentação de dashboards interativos no Power BI.
* **Alertas e Notificações:** Envio automático da lista de chamada do dia para o e-mail do professor responsável.

## 🛠️ Tecnologias e Arquitetura

O projeto foi construído utilizando as seguintes tecnologias:

* **Linguagem Principal:** Python
* **Interface Gráfica (Desktop):** Tkinter / CustomTkinter
* **Banco de Dados Local:** SQLite (focado em leveza e resiliência para rodar no PC do professor)
* **Banco de Dados em Nuvem:** Supabase (PostgreSQL) para backup e persistência remota
* **Análise de Dados:** Power BI (Dashboards e painéis gerenciais de frequência)
* **Integração de Hardware:** Bibliotecas de interpretação de sinais HID (leitor de código de barras USB)
* **Empacotamento:** Inno Setup (para compilação e geração do instalador `.exe`)

## 👥 Equipe de Desenvolvimento

Este projeto foi construído de forma colaborativa, simulando um ambiente real de desenvolvimento de software:

* **João Pedro Faria Das Neves Da Silva** - *Desenvolvedor Principal (Backend e Dados)*
  * Estruturação da lógica principal em Python.
  * Modelagem e administração do banco de dados (SQLite + Supabase).
  * Desenvolvimento dos painéis analíticos e métricas no Power BI.

* **Gabriel Oliveira** - *Designer de Interface (UI/UX)*
  * Idealização e desenho da interface visual do aplicativo.

* **Gabriel Miguel** - *Desenvolvedor Frontend e Integração*
  * Implementação da interface no código da aplicação e correção de bugs estruturais.

* **Allan** - *Analista de Qualidade e Testes (QA)*
  * Testes ativos no sistema, identificação de falhas e sugestões de melhorias contínuas na usabilidade.

## ⚙️ Como Executar o Projeto

**Pré-requisitos:** Python 3.10+ instalado no computador.

1. Clone este repositório:
   ```bash
   git clone [https://github.com/SEU-USUARIO/SAPA.git](https://github.com/SEU-USUARIO/SAPA.git)
