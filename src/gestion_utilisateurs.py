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

    # Style CSS moderne et épuré
    st.markdown(
        """
        <style>
        .stApp { background: #f8fafc; color: #0f172a; }

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
            background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
            color: #ffffff !important;
            border: none !important;
            padding: 0.6rem 1.2rem;
            font-weight: 600;
            border-radius: 10px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            transition: all 0.2s ease;
        }
        [data-testid="stSidebar"] div.stButton > button *,
        [data-testid="stSidebar"] div.stButton > button p {
            color: #ffffff !important;
        }
        [data-testid="stSidebar"] div.stButton > button:hover {
            background: linear-gradient(135deg, #047857 0%, #065f46 100%) !important;
            box-shadow: 0 6px 8px -1px rgba(0, 0, 0, 0.15);
            transform: translateY(-1px);
        }

        .users-hero {
            padding: 2rem 2.2rem;
            border-radius: 16px;
            margin-bottom: 1.5rem;
            color: #ffffff;
            background: linear-gradient(135deg, #065f46 0%, #059669 100%);
            box-shadow: 0 10px 25px -5px rgba(5, 150, 105, 0.2);
        }
        .users-hero h1 { margin: 0; color: #ffffff !important; font-size: 2rem; font-weight: 800; }
        .users-hero p { margin: 0.5rem 0 0; color: #a7f3d0 !important; font-size: 1rem; }

        [data-testid="stTextInput"] input {
            min-height: 2.75rem;
            background: #f9fafb !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            opacity: 1 !important;
        }
        [data-testid="stTextInput"] input:focus {
            border-color: #059669 !important;
            box-shadow: 0 0 0 2px rgba(5, 150, 105, 0.2) !important;
        }
        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] *,
        [data-baseweb="select"] *,
        [data-testid="stCheckbox"] label,
        [data-testid="stCheckbox"] label p {
            color: #0f172a !important;
        }
        </style>
        <div class="users-hero">
            <h1>👥 Gestion des utilisateurs</h1>
            <p>Administration centralisée des accès et des rôles de la plateforme WeedsGalore.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        database_settings = _read_database_settings()
        roles = list_roles(database_settings)
        users = list_users(database_settings)
    except psycopg.Error:
        st.error("Impossible de charger les données utilisateurs depuis PostgreSQL.")
        return

    if not roles:
        st.error("Aucun rôle n’est configuré dans la base de données.")
        return

    role_ids = [role[0] for role in roles]
    role_names = [role[1] for role in roles]
    user_by_username = {user[0]: user for user in users}

    # Gestion des états de session pour l'affichage conditionnel
    if "show_create_form" not in st.session_state:
        st.session_state.show_create_form = False
    if "editing_username" not in st.session_state:
        st.session_state.editing_username = None
    if "deleting_username" not in st.session_state:
        st.session_state.deleting_username = None

    # --- 1. FORMULAIRE DE CRÉATION (S'affiche tout en haut si actif) ---
    if st.session_state.show_create_form:
        with st.container(border=True):
            st.subheader("Créer un nouveau compte utilisateur")
            st.caption(
                "Renseignez les informations d’identité et de connexion. "
                "Le prénom et l’adresse e-mail sont facultatifs."
            )
            with st.form("user-create-form", clear_on_submit=True):

                identity_first, identity_last = st.columns(2)
                with identity_first:
                    first_name = st.text_input("Prénom", max_chars=100)
                with identity_last:
                    name = st.text_input("Nom *", max_chars=100)

                account_username, account_email = st.columns(2)
                with account_username:
                    username = st.text_input(
                        "Nom d’utilisateur *",
                        max_chars=50,
                        help="3 à 50 caractères : lettres, chiffres, point, tiret ou souligné.",
                    )
                with account_email:
                    email = st.text_input("Adresse e-mail", max_chars=100)

                account_password, account_role = st.columns(2)
                with account_password:
                    password = st.text_input(
                        "Mot de passe temporaire *",
                        type="password",
                        help="Le mot de passe doit contenir au moins 12 caractères.",
                    )
                with account_role:
                    role_index = st.selectbox(
                        "Rôle applicatif",
                        range(len(roles)),
                        format_func=lambda i: role_names[i],
                    )

                active = st.checkbox("Activer le compte immédiatement", value=True)

                c_sub, c_cancel = st.columns(2)
                with c_sub:
                    submitted = st.form_submit_button(
                        "Créer l’utilisateur",
                        type="primary",
                        use_container_width=True,
                    )
                with c_cancel:
                    cancelled = st.form_submit_button("Annuler", use_container_width=True)

            if cancelled:
                st.session_state.show_create_form = False
                st.rerun()

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
                    st.error("Ce nom d’utilisateur est déjà utilisé.")
                except psycopg.Error:
                    st.error("Erreur serveur lors de la création du compte.")
                else:
                    st.success("L'utilisateur a été créé avec succès.")
                    st.session_state.show_create_form = False
                    st.rerun()
        st.divider()

    # --- 2. FORMULAIRE D'ÉDITION (S'affiche tout en haut si actif) ---
    if st.session_state.editing_username:
        edit_u = user_by_username.get(st.session_state.editing_username)
        if edit_u:
            username, name, first_name, email, role_id, _, active = edit_u
            with st.container(border=True):
                st.subheader(f"Modifier le compte : {username}")
                with st.form("user-edit-form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        edited_first_name = st.text_input(
                            "Prénom", value=first_name or "", max_chars=100
                        )
                        edited_email = st.text_input(
                            "Adresse e-mail", value=email or "", max_chars=100
                        )
                    with col2:
                        edited_name = st.text_input(
                            "Nom *", value=name, max_chars=100
                        )
                        selected_role = st.selectbox(
                            "Rôle applicatif",
                            range(len(roles)),
                            index=role_ids.index(role_id) if role_id in role_ids else 0,
                            format_func=lambda i: role_names[i],
                        )

                    edited_active = st.checkbox("Compte actif", value=active)
                    new_password = st.text_input(
                        "Nouveau mot de passe (facultatif)",
                        type="password",
                        help="Laissez vide pour conserver le mot de passe actuel.",
                    )

                    c_upd, c_close = st.columns(2)
                    with c_upd:
                        update_submitted = st.form_submit_button(
                            "Enregistrer les modifications",
                            type="primary",
                            use_container_width=True,
                        )
                    with c_close:
                        close_edited = st.form_submit_button("Annuler", use_container_width=True)

                if close_edited:
                    st.session_state.editing_username = None
                    st.rerun()

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
                    except psycopg.Error:
                        st.error("Impossible de mettre à jour le compte.")
                    else:
                        st.success("Modifications enregistrées.")
                        st.session_state.editing_username = None
                        st.rerun()
        st.divider()

    # --- 3. FORMULAIRE DE CONFIRMATION DE SUPPRESSION (S'affiche en haut si actif) ---
    if st.session_state.deleting_username:
        del_user_target = st.session_state.deleting_username
        with st.container(border=True):
            st.error(f"⚠️ Confirmation requise : Suppression définitive du compte `{del_user_target}`")
            with st.form("user-delete-confirm-form"):
                confirm_check = st.checkbox("Je confirme vouloir supprimer définitivement ce compte.")
                c_del, c_cancel_del = st.columns(2)
                with c_del:
                    delete_confirmed = st.form_submit_button(
                        "Confirmer la suppression",
                        type="primary",
                        use_container_width=True,
                    )
                with c_cancel_del:
                    cancel_delete = st.form_submit_button("Annuler", use_container_width=True)

            if cancel_delete:
                st.session_state.deleting_username = None
                st.rerun()

            if delete_confirmed:
                if not confirm_check:
                    st.warning("Veuillez cocher la case de confirmation pour procéder.")
                else:
                    try:
                        delete_user(
                            database_settings,
                            del_user_target,
                            current_username=current_user["username"],
                        )
                    except ValueError as error:
                        st.error(str(error))
                    except psycopg.Error:
                        st.error("Erreur lors de la suppression.")
                    else:
                        st.success(f"Compte {del_user_target} supprimé avec succès.")
                        st.session_state.deleting_username = None
                        st.rerun()
        st.divider()

    # --- 4. TITRE DE L'ANNUAIRE ET BOUTON D'AJOUT ---
    col_title, col_btn = st.columns([3, 1])
    with col_title:
        st.subheader("📋 Annuaire des utilisateurs")
    with col_btn:
        if st.button("Nouvel utilisateur", type="primary", use_container_width=True):
            st.session_state.show_create_form = not st.session_state.show_create_form
            st.session_state.editing_username = None
            st.session_state.deleting_username = None
            st.rerun()

    st.divider()

    # --- 5. TABLEAU INTERACTIF DES UTILISATEURS AVEC COLONNE ACTIONS ---
    if users:
        column_widths = [2.0, 2.2, 2.4, 1.1, 1.1, 1.3]
        headers = st.columns(column_widths)
        for column, title in zip(
            headers,
            [
                "Nom d’utilisateur",
                "Nom complet",
                "Adresse e-mail",
                "Rôle",
                "Statut",
                "Actions",
            ],
        ):
            column.markdown(f"**{title}**")
        st.divider()

        for username, name, first_name, email, _, role_name, active in users:
            with st.container():
                cols = st.columns(column_widths)
                cols[0].write(f"**{username}**")
                cols[1].write(
                    " ".join(part for part in (first_name, name) if part) or "-"
                )
                cols[2].write(email or "-")
                cols[3].write(role_name)
                cols[4].write("🟢 Actif" if active else "🔴 Inactif")

                # Boutons d'actions par ligne (Éditer / Supprimer)
                action_col1, action_col2 = cols[5].columns(2)
                with action_col1:
                    if st.button(
                        "✏️",
                        key=f"edit_{username}",
                        help=f"Modifier {username}",
                        use_container_width=True,
                    ):
                        st.session_state.editing_username = username
                        st.session_state.show_create_form = False
                        st.session_state.deleting_username = None
                        st.rerun()
                with action_col2:
                    is_self = (username == current_user["username"])
                    if st.button(
                        "🗑️",
                        key=f"del_{username}",
                        help=f"Supprimer {username}",
                        disabled=is_self,
                        use_container_width=True,
                    ):
                        st.session_state.deleting_username = username
                        st.session_state.show_create_form = False
                        st.session_state.editing_username = None
                        st.rerun()
                st.divider()
    else:
        st.info("Aucun compte utilisateur n’est enregistré dans la base de données.")