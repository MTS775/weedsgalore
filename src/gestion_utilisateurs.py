# SPDX-FileCopyrightText: 2025 Helmholtz Centre Potsdam - GFZ German Research Centre for Geosciences
# SPDX-License-Identifier: Apache-2.0

import psycopg
import streamlit as st
from psycopg.errors import UniqueViolation

from connexion_streamlit import (
    _read_database_settings,
    create_user,
    delete_user,
    list_roles,
    list_users,
    update_user,
)


def render_user_management(current_user):
    if current_user["role"] != "admin":
        st.error("L’administration des comptes est réservée aux administrateurs.")
        return

    st.markdown(
        """
        <style>
        .stApp {
            background: #f8fafc;
            color: #0f172a;
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
            border-right: 1px solid #334155;
        }
        [data-testid="stSidebar"] *,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p {
            color: #f1f5f9 !important;
        }
        [data-testid="stSidebar"] div.stButton > button {
            background: linear-gradient(135deg, #059669 0%, #047857 100%);
            color: #ffffff !important;
            border: none;
            padding: 0.6rem 1.2rem;
            font-weight: 600;
            border-radius: 10px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            transition: all 0.2s ease;
        }
        [data-testid="stSidebar"] div.stButton > button:hover {
            background: linear-gradient(135deg, #047857 0%, #065f46 100%);
            box-shadow: 0 6px 8px -1px rgba(0, 0, 0, 0.15);
            transform: translateY(-1px);
        }
        .users-hero {
            padding: 2rem 2.2rem;
            border-radius: 20px;
            margin-bottom: 1.5rem;
            color: #ffffff;
            background: linear-gradient(135deg, #065f46 0%, #047857 50%, #059669 100%);
            box-shadow: 0 10px 25px -5px rgba(5, 150, 105, 0.25),
                0 8px 10px -6px rgba(5, 150, 105, 0.25);
        }
        .users-hero h1 {
            margin: 0;
            color: #ffffff !important;
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.025em;
        }
        .users-hero p {
            margin: 0.5rem 0 0;
            color: #a7f3d0 !important;
            font-size: 1.05rem;
        }
        [data-baseweb="tab"],
        [data-baseweb="tab"] p,
        [data-baseweb="tab"] span {
            color: #000000 !important;
            font-weight: 600;
        }
        [data-baseweb="tab"]:hover,
        [data-baseweb="tab"][aria-selected="true"] {
            background-color: #e8f5e9 !important;
        }
        [data-baseweb="tab-highlight"] {
            background-color: #16803c !important;
        }
        [data-testid="stForm"] {
            padding: 1.5rem;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            background: #ffffff;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
        }
        [data-testid="stForm"] [data-testid="stWidgetLabel"],
        [data-testid="stForm"] [data-testid="stWidgetLabel"] *,
        [data-testid="stForm"] label,
        [data-testid="stForm"] label p {
            color: #0f172a !important;
            font-weight: 600;
        }
        [data-testid="stForm"] [data-testid="stTextInput"] input {
            min-height: 2.75rem;
            background: #f8fafc !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            opacity: 1 !important;
        }
        [data-testid="stForm"] [data-testid="stTextInput"] input:focus {
            border-color: #059669 !important;
            box-shadow: 0 0 0 2px rgba(5, 150, 105, 0.2) !important;
        }
        [data-testid="stForm"] [data-baseweb="select"] > div {
            min-height: 2.75rem;
            background: #f8fafc !important;
            border-color: #cbd5e1 !important;
        }
        [data-testid="stForm"] [data-baseweb="select"] *,
        [data-testid="stForm"] [data-baseweb="select"] input {
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
        }
        [data-testid="stForm"] [data-testid="stCheckbox"] label,
        [data-testid="stForm"] [data-testid="stCheckbox"] label p {
            color: #0f172a !important;
        }
        div.stButton > button[kind="primary"],
        [data-testid="stFormSubmitButton"] > button {
            border: none;
            border-radius: 10px;
            background: linear-gradient(135deg, #059669 0%, #047857 100%);
            color: #ffffff !important;
            font-weight: 600;
        }
        [data-testid="stDataFrame"] {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            background: #ffffff;
        }
        </style>
        <div class="users-hero">
            <h1>👥 Gestion des utilisateurs</h1>
            <p>Créer, consulter et gérer les accès à la plateforme WeedsGalore.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        database_settings = _read_database_settings()
        roles = list_roles(database_settings)
        users = list_users(database_settings)
    except psycopg.Error:
        st.error("Impossible de charger les utilisateurs et les rôles depuis PostgreSQL.")
        return

    if not roles:
        st.error("Aucun rôle n’est configuré dans la table roles.")
        return

    role_ids = [role[0] for role in roles]
    role_names = [role[1] for role in roles]
    user_by_username = {user[0]: user for user in users}

    tab_list, tab_create, tab_edit, tab_delete = st.tabs(
        ["Liste", "Créer", "Modifier", "Supprimer"]
    )

    with tab_list:
        if users:
            st.dataframe(
                [
                    {
                        "Username": username,
                        "Prénom": first_name or "",
                        "Nom": name,
                        "E-mail": email or "",
                        "Rôle": role_name,
                        "Actif": active,
                    }
                    for username, name, first_name, email, _, role_name, active in users
                ],
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("Aucun compte utilisateur n’est encore enregistré.")

    with tab_create:
        with st.form("user-create-form", clear_on_submit=True):
            username = st.text_input("Username *", max_chars=50)
            first_name = st.text_input("Prénom", max_chars=100)
            name = st.text_input("Nom *", max_chars=100)
            email = st.text_input("E-mail", max_chars=100)
            password = st.text_input(
                "Mot de passe * (12 caractères minimum)", type="password"
            )
            role_index = st.selectbox(
                "Rôle", range(len(roles)), format_func=lambda index: role_names[index]
            )
            active = st.checkbox("Compte actif", value=True)
            submitted = st.form_submit_button("Créer l’utilisateur", type="primary")

        if submitted:
            try:
                create_user(
                    database_settings,
                    username,
                    name,
                    email,
                    password,
                    role_ids[role_index],
                    active,
                    prenom=first_name,
                )
            except ValueError as error:
                st.error(str(error))
            except UniqueViolation:
                st.error("Ce username existe déjà.")
            except psycopg.Error:
                st.error("Impossible de créer l’utilisateur dans PostgreSQL.")
            else:
                st.success("Utilisateur créé.")
                st.rerun()

    with tab_edit:
        if not users:
            st.info("Aucun utilisateur à modifier.")
        else:
            selected_username = st.selectbox(
                "Utilisateur à modifier",
                list(user_by_username),
                key="user-edit-selection",
            )
            username, name, first_name, email, role_id, _, active = user_by_username[
                selected_username
            ]
            with st.form("user-edit-form"):
                st.text_input("Username", value=username, disabled=True)
                edited_first_name = st.text_input(
                    "Prénom", value=first_name or "", max_chars=100
                )
                edited_name = st.text_input("Nom *", value=name, max_chars=100)
                edited_email = st.text_input(
                    "E-mail", value=email or "", max_chars=100
                )
                selected_role = st.selectbox(
                    "Rôle",
                    range(len(roles)),
                    index=role_ids.index(role_id),
                    format_func=lambda index: role_names[index],
                )
                edited_active = st.checkbox("Compte actif", value=active)
                new_password = st.text_input(
                    "Nouveau mot de passe (laisser vide pour ne pas changer)",
                    type="password",
                )
                update_submitted = st.form_submit_button(
                    "Enregistrer les modifications", type="primary"
                )
            if update_submitted:
                try:
                    update_user(
                        database_settings,
                        username,
                        edited_name,
                        edited_email,
                        role_ids[selected_role],
                        edited_active,
                        new_password or None,
                        current_username=current_user["username"],
                        prenom=edited_first_name,
                    )
                except ValueError as error:
                    st.error(str(error))
                except UniqueViolation:
                    st.error("Un utilisateur avec ces informations existe déjà.")
                except psycopg.Error:
                    st.error("Impossible de modifier l’utilisateur dans PostgreSQL.")
                else:
                    st.success("Utilisateur modifié.")
                    st.rerun()

    with tab_delete:
        deletable_users = [
            username
            for username in user_by_username
            if username != current_user["username"]
        ]
        if not deletable_users:
            st.info("Aucun autre utilisateur ne peut être supprimé.")
        else:
            delete_username = st.selectbox(
                "Utilisateur à supprimer",
                deletable_users,
                key="user-delete-selection",
            )
            confirm = st.checkbox(
                "Je confirme la suppression définitive de ce compte.",
                key="user-delete-confirm",
            )
            if st.button(
                "Supprimer l’utilisateur",
                type="primary",
                disabled=not confirm,
                key="user-delete-submit",
            ):
                try:
                    delete_user(
                        database_settings,
                        delete_username,
                        current_username=current_user["username"],
                    )
                except ValueError as error:
                    st.error(str(error))
                except psycopg.Error:
                    st.error("Impossible de supprimer l’utilisateur dans PostgreSQL.")
                else:
                    st.success("Utilisateur supprimé.")
                    st.rerun()
