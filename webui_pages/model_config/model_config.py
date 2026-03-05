import hashlib
import streamlit as st
from webui_pages.utils import ApiRequest
from webui_pages.translations import get_text


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _auth_header() -> dict:
    token = st.session_state.get("auth_token", "")
    return {"Authorization": token}


def _api_call(api: ApiRequest, method: str, url: str, **kwargs):
    """Make API call with auth header, return parsed JSON or None on error."""
    kwargs["headers"] = {**_auth_header(), **kwargs.get("headers", {})}
    try:
        resp = getattr(api, method)(url, **kwargs)
        return resp.json() if resp else None
    except Exception:
        return None


def _list_users(api: ApiRequest):
    result = _api_call(api, "get", "/auth/list_users")
    if result and result.get("code") == 200:
        return result.get("data", [])
    return []


def model_config_page(api: ApiRequest, is_lite: bool = False):
    lang = st.session_state.get("language", "tr")
    t = lambda key: get_text(lang, key)

    st.title(t("user_management"))

    # ── User List ─────────────────────────────────────────────────────────────
    st.subheader(t("user_list"))

    if st.button(t("refresh"), key="refresh_users"):
        st.session_state.pop("_users_cache", None)

    if "_users_cache" not in st.session_state:
        st.session_state["_users_cache"] = _list_users(api)

    users = st.session_state["_users_cache"]

    if not users:
        st.info(t("no_user"))
    else:
        current_user_id = st.session_state.get("user_info", {}).get("user_id")

        for u in users:
            col_name, col_role, col_status, col_toggle, col_pwd, col_del = st.columns(
                [2.5, 1.5, 1.2, 1.2, 1.2, 1.2]
            )
            with col_name:
                st.markdown(f"**{u['username']}**")
            with col_role:
                role_label = u.get("role", "user").capitalize()
                st.markdown(f"`{role_label}`")
            with col_status:
                status_label = t("active") if u.get("is_active") else t("inactive")
                color = "green" if u.get("is_active") else "red"
                st.markdown(f":{color}[{status_label}]")
            with col_toggle:
                is_self = u["id"] == current_user_id
                if not u.get("role") == "admin" and not is_self:
                    btn_label = t("deactivate") if u.get("is_active") else t("activate")
                    if st.button(btn_label, key=f"toggle_{u['id']}"):
                        res = _api_call(
                            api, "post", "/auth/toggle_user",
                            json={"user_id": u["id"]},
                        )
                        if res and res.get("code") == 200:
                            st.success(res.get("msg", t("success")))
                            st.session_state.pop("_users_cache", None)
                            st.rerun()
                        else:
                            st.error(res.get("msg", t("error")) if res else t("error"))
            with col_pwd:
                if st.button(t("change_password_short"), key=f"pwd_{u['id']}"):
                    st.session_state["_pwd_user_id"] = u["id"]
                    st.session_state["_pwd_username"] = u["username"]
            with col_del:
                if not u.get("role") == "admin" and not is_self:
                    if st.button(t("delete"), key=f"del_{u['id']}"):
                        st.session_state["_del_confirm_id"] = u["id"]
                        st.session_state["_del_confirm_name"] = u["username"]

            st.divider()

    # ── Delete Confirmation ───────────────────────────────────────────────────
    if "_del_confirm_id" in st.session_state:
        uid = st.session_state["_del_confirm_id"]
        uname = st.session_state["_del_confirm_name"]
        st.warning(f"{t('delete_confirm')} **{uname}**?")
        col_yes, col_no, _ = st.columns([1, 1, 4])
        with col_yes:
            if st.button(t("yes"), key="del_yes"):
                res = _api_call(
                    api, "post", "/auth/delete_user",
                    json={"user_id": uid},
                )
                if res and res.get("code") == 200:
                    st.success(res.get("msg", t("success")))
                    st.session_state.pop("_users_cache", None)
                else:
                    st.error(res.get("msg", t("error")) if res else t("error"))
                st.session_state.pop("_del_confirm_id", None)
                st.session_state.pop("_del_confirm_name", None)
                st.rerun()
        with col_no:
            if st.button(t("no"), key="del_no"):
                st.session_state.pop("_del_confirm_id", None)
                st.session_state.pop("_del_confirm_name", None)
                st.rerun()

    # ── Change Password ───────────────────────────────────────────────────────
    if "_pwd_user_id" in st.session_state:
        uid = st.session_state["_pwd_user_id"]
        uname = st.session_state["_pwd_username"]
        st.subheader(f"{t('change_password')}: {uname}")
        with st.form("change_pwd_form"):
            new_pwd = st.text_input(t("new_password"), type="password")
            new_pwd2 = st.text_input(t("new_password_confirm"), type="password")
            submitted = st.form_submit_button(t("save"))
            if submitted:
                if not new_pwd or len(new_pwd) < 6:
                    st.error(t("password_too_short"))
                elif new_pwd != new_pwd2:
                    st.error(t("password_mismatch"))
                else:
                    res = _api_call(
                        api, "post", "/auth/change_password",
                        json={"user_id": uid, "new_password": _hash_password(new_pwd)},
                    )
                    if res and res.get("code") == 200:
                        st.success(res.get("msg", t("success")))
                        st.session_state.pop("_pwd_user_id", None)
                        st.session_state.pop("_pwd_username", None)
                        st.rerun()
                    else:
                        st.error(res.get("msg", t("error")) if res else t("error"))
        if st.button(t("cancel"), key="cancel_pwd"):
            st.session_state.pop("_pwd_user_id", None)
            st.session_state.pop("_pwd_username", None)
            st.rerun()

    # ── Create User ───────────────────────────────────────────────────────────
    st.subheader(t("create_user"))
    with st.form("create_user_form"):
        new_username = st.text_input(t("username"))
        new_password = st.text_input(t("password"), type="password")
        new_role = st.selectbox(t("role"), options=["user", "admin"])
        submitted = st.form_submit_button(t("create_user_button"))
        if submitted:
            if not new_username or not new_password:
                st.error(t("fill_all_fields"))
            elif len(new_password) < 6:
                st.error(t("password_too_short"))
            else:
                res = _api_call(
                    api, "post", "/auth/create_user",
                    json={
                        "username": new_username,
                        "password": _hash_password(new_password),
                        "role": new_role,
                    },
                )
                if res and res.get("code") == 200:
                    st.success(res.get("msg", t("success")))
                    st.session_state.pop("_users_cache", None)
                    st.rerun()
                else:
                    st.error(res.get("msg", t("error")) if res else t("error"))
