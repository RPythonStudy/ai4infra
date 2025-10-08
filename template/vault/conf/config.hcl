pid_file = "/tmp/vault-agent-pid"

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path = "/agent/role_id"
      secret_id_file_path = "/agent/secret_id"
    }
  }
  sink "file" {
    config = {
      path = "/sink/agent-token"
    }
  }
}

template {
  source      = "/agent/template.ctmpl"
  destination = "/sink/rendered_secret"
}
