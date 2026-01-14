-- oidc_auth.lua
local openidc = require("resty.openidc")

local function validate()
    -- 1. 환경변수 로드
    local provider = os.getenv("OIDC_PROVIDER") or "google"
    local client_id = os.getenv("OIDC_CLIENT_ID")
    local client_secret = os.getenv("OIDC_CLIENT_SECRET")
    local cookie_secret = os.getenv("OIDC_COOKIE_SECRET")

    -- 2. Discovery URL 결정 (Hybrid Strategy)
    local discovery_url
    if provider == "keycloak" then
        discovery_url = "http://ai4infra-keycloak:8080/realms/ai4infra/.well-known/openid-configuration"
    else
        -- Default: Google
        discovery_url = "https://accounts.google.com/.well-known/openid-configuration"
    end

    -- 3. 설정 검증 (필수값 누락 시 에러 로그)
    if not client_id or not client_secret or not cookie_secret then
        ngx.log(ngx.ERR, "[OIDC] 필수 환경변수 누락 (CLIENT_ID/SECRET/COOKIE_SECRET)")
        return ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
    end

    -- 4. OIDC 인증 수행
    local opts = {
        redirect_uri = "/redirect_uri",
        discovery = discovery_url,
        client_id = client_id,
        client_secret = client_secret,
        redirect_uri_scheme = "https",
        logout_path = "/logout",
        redirect_after_logout_uri = "/",
        redirect_after_logout_with_id_token_hint = false,
        session_contents = {id_token=true},
        ssl_verify = "no", -- 내부망 및 자체 서명 인증서 호환 (Production에서는 'yes' 권장)
        accept_bearer_token = true, -- [SEC-04] Hybrid Mode (Browser + API)
        iat_slack = 600 -- [Fix] Clock Skew 허용 (10분)
    }
    
    -- [SEC-04] Pre-Validation: Bearer Token 검증 우선 처리 (API 요청 시 Redirect 방지)
    -- local auth_header = ngx.req.get_headers()["Authorization"] -- Debug Log Remove
    local auth_header = ngx.req.get_headers()["Authorization"]
    if auth_header and string.find(auth_header, "Bearer") then
        local json_token, verify_err = openidc.bearer_jwt_verify(opts)
        if json_token then
            -- ngx.log(ngx.ERR, "[RBAC] Pre-Validation Success: " .. (json_token.preferred_username or "unknown"))
            -- Set Headers and Context manually
            ngx.req.set_header("X-User-Email", json_token.email)
            ngx.req.set_header("X-User-Name", json_token.name)
            
            -- RBAC Role Parsing
            local roles = {}
            if json_token.realm_access and json_token.realm_access.roles then
                roles = json_token.realm_access.roles
            elseif json_token.roles then
                roles = json_token.roles
            end
            if type(roles) ~= "table" then roles = { roles } end
            ngx.ctx.user_roles = roles
            ngx.req.set_header("X-User-Roles", table.concat(roles, ","))
            
            -- Skip openidc.authenticate and return success
            return
        else
            ngx.log(ngx.ERR, "[RBAC] Pre-Validation Failed: " .. (verify_err or "unknown") .. ". Falling back to standard auth.")
            -- Proceed to authenticate (Standard Flow)
        end
    end

    -- 인증 호출 (Session/Cookie Flow)
    local res, err = openidc.authenticate(opts, cookie_secret)

    if err then
        ngx.status = 500
        ngx.say(err)
        ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
    end

    -- 5. 인증 성공 시 헤더 주입 (백엔드로 사용자 정보 전달)
    if res and res.id_token then
         ngx.req.set_header("X-User-Email", res.id_token.email)
         ngx.req.set_header("X-User-Name", res.id_token.name)
         
         -- [SEC-04] RBAC: ID Token에서 역할(Roles) 파싱
         -- Keycloak은 기본적으로 realm_access.roles에 역할을 담습니다.
         local roles = {}
         if res.id_token.realm_access and res.id_token.realm_access.roles then
             roles = res.id_token.realm_access.roles
         elseif res.id_token.roles then
             roles = res.id_token.roles
         end
         
         -- Lua table로 변환 (이미 table일 수 있음)
         if type(roles) ~= "table" then
            roles = { roles }
         end
         
         -- ngx.ctx에 저장하여 후속 호출(require_role)에서 사용
         ngx.ctx.user_roles = roles
         
         -- [Debug] 로그 출력
         ngx.log(ngx.ERR, "[RBAC Debug] User: " .. (res.id_token.preferred_username or "unknown") .. ", Roles: " .. table.concat(roles, ","))
         
         -- 디버깅용 헤더 (운영 시 제거 권장)
         ngx.req.set_header("X-User-Roles", table.concat(roles, ","))
    end
end

-- 역할 보유 여부 확인 (Helper)
local function has_role(role_name)
    local roles = ngx.ctx.user_roles or {}
    ngx.log(ngx.ERR, "[RBAC Debug] Checking role: " .. role_name .. " against user roles: " .. table.concat(roles, ","))
    for _, r in ipairs(roles) do
        if r == role_name then
            return true
        end
    end
    return false
end

-- 역할 강제 (접근 제어)
local function require_role(role_name)
    -- 먼저 인증 수행 (validate가 먼저 호출되어야 함)
    -- 하지만 require_role만 단독 호출될 수도 있으므로..
    -- 보통 access_by_lua_block에서 validate() -> require_role() 순서로 호출함.
    
    if not has_role(role_name) then
        ngx.log(ngx.WARN, "[RBAC] Access Denied: User missing role: " .. role_name)
        ngx.status = 403
        ngx.say("403 Forbidden: You do not have the required role (" .. role_name .. ").")
        return ngx.exit(ngx.HTTP_FORBIDDEN)
    end
end

return {
    validate = validate,
    require_role = require_role,
    has_role = has_role
}
