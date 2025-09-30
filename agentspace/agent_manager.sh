#!/bin/bash
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# agent_manager.sh: Script to manage AgentSpace agents
# Adheres to Google Shell Style Guide (go/shell-style)

# --- Configuration ---
# Loads configuration from .env file.
_load_env() {
  if [[ ! -f ".env" ]]; then
    echo "Error: .env file not found. Please create one from .env.sample." >&2
    exit 1
  fi
  set -a # Automatically export all variables
  source .env
  set +a # Stop automatically exporting
}

_load_env

# --- URL Construction ---
BASE_URL="https://discoveryengine.googleapis.com/v1alpha"
AGENT_BASE_URL="${BASE_URL}/projects/${GCP_PROJECT_NUMBER}/locations/${LOCATION}/collections/${COLLECTION_ID}/engines/${ENGINE_ID}/assistants/${ASSISTANT_ID}/agents"

# --- Helper Functions ---

# Retrieves the gcloud auth token.
# Exits if gcloud command fails.
_get_token() {
  local token
  token=$(gcloud auth print-access-token)
  if (( $? != 0 )); then
    echo "Error: Failed to get gcloud auth token." >&2
    exit 1
  fi
  echo "${token}"
}

# Executes the curl command with common headers.
# @param {string} method The HTTP method (GET, POST, DELETE, PATCH).
# @param {string} url The target URL.
# @param {...string} args Additional arguments to pass to curl.
_curl_cmd() {
  local method="$1"
  local url="$2"
  shift 2
  local token
  token=$(_get_token)

  curl -s -X "${method}" \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json" \
    -H "x-goog-user-project: ${PROJECT_ID}" \
    "$@" \
    "${url}"
}

# --- API Functions ---

# Lists all agents.
list_agents() {
  echo "Listing agents..."
  _curl_cmd "GET" "${AGENT_BASE_URL}"
  echo # Newline for better formatting
}

# Deletes a specific agent by ID.
# @param {string} agent_id The ID of the agent to delete.
delete_agent() {
  local agent_id="$1"
  if [[ -z "${agent_id}" ]]; then
    echo "Error: Agent ID is required for delete." >&2
    return 1
  fi
  echo "Deleting agent: ${agent_id}..."
  _curl_cmd "DELETE" "${AGENT_BASE_URL}/${agent_id}"
  echo # Newline
}

# Creates a new agent from a JSON file.
# @param {string} json_file Path to the JSON file containing agent data.
create_agent() {
  local json_file="$1"
  if [[ -z "${json_file}" ]]; then
    echo "Error: JSON file path is required for create." >&2
    return 1
  fi
  if [[ ! -f "${json_file}" ]]; then
    echo "Error: JSON file not found: ${json_file}" >&2
    return 1
  fi
  echo "Creating agent from ${json_file}..."
  _curl_cmd "POST" "${AGENT_BASE_URL}" -d "@${json_file}"
  echo # Newline
}

# Updates an existing agent by ID using data from a JSON file.
# @param {string} agent_id The ID of the agent to update.
# @param {string} json_file Path to the JSON file containing agent data.
update_agent() {
  local agent_id="$1"
  local json_file="$2"
  if [[ -z "${agent_id}" ]]; then
    echo "Error: Agent ID is required for update." >&2
    return 1
  fi
  if [[ -z "${json_file}" ]]; then
    echo "Error: JSON file path is required for update." >&2
    return 1
  fi
  if [[ ! -f "${json_file}" ]]; then
    echo "Error: JSON file not found: ${json_file}" >&2
    return 1
  fi
  echo "Updating agent: ${agent_id} from ${json_file}..."
  _curl_cmd "PATCH" "${AGENT_BASE_URL}/${agent_id}" -d "@${json_file}"
  echo # Newline
}

# --- Usage ---
usage() {
  echo "Usage: $0 {list|delete|create|update} [options]"
  echo "Commands:"
  echo "  list                List all agents."
  echo "  delete <agent_id>   Delete the specified agent."
  echo "  create <json_file>  Create an agent from the JSON file."
  echo "  update <agent_id> <json_file> Update the specified agent with data from the JSON file."
}

# --- Main ---
main() {
  local action="$1"
  if [[ -z "${action}" ]]; then
    usage
    exit 1
  fi
  shift

  case "${action}" in
    list)
      list_agents
      ;;
    delete)
      delete_agent "$1"
      ;;
    create)
      create_agent "$1"
      ;;
    update)
      update_agent "$1" "$2"
      ;;
    *)
      echo "Error: Unknown action: ${action}" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
