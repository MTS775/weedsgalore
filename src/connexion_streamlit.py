# SPDX-FileCopyrightText: 2025 Helmholtz Centre Potsdam - GFZ German Research Centre for Geosciences
# SPDX-License-Identifier: Apache-2.0

import hashlib
import hmac
import base64
import re
import secrets

import psycopg
import streamlit as st


PASSWORD_ITERATIONS = 600_000
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")


class AuthenticationConfigurationError(ValueError):
    pass


def hash_password(password):
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return encode_password_hash(salt, password_hash, PASSWORD_ITERATIONS)


def encode_password_hash(salt, password_hash, iterations):
    encoded_salt = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    encoded_hash = base64.urlsafe_b64encode(password_hash).decode("ascii").rstrip("=")
    return "$pbkdf2_sha256${}${}${}".format(
        iterations, encoded_salt, encoded_hash
    )


def verify_password(password, stored_hash):
    try:
        algorithm, scheme, iteration_text, encoded_salt, encoded_hash = stored_hash.split("$")
        if algorithm or scheme != "pbkdf2_sha256":
            return False
        iterations = int(iteration_text)
        if iterations < 1:
            return False
        salt = base64.urlsafe_b64decode(encoded_salt + "=" * (-len(encoded_salt) % 4))
        expected_hash = base64.urlsafe_b64decode(
            encoded_hash + "=" * (-len(encoded_hash) % 4)
        )
    except (AttributeError, ValueError):
        return False
    actual_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(actual_hash, expected_hash)


def validate_username(username):
    normalized = username.strip()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Le username doit contenir 3 à 50 caractères : lettres, chiffres, "
            "point, tiret ou souligné."
        )
    return normalized


def validate_password(password):
    if len(password) < 12:
        raise ValueError("Le mot de passe doit contenir au moins 12 caractères.")
    if len(password) > 256:
        raise ValueError("Le mot de passe ne peut pas dépasser 256 caractères.")
    return password


def validate_user_fields(username, name, email, password=None, prenom=None):
    normalized_username = validate_username(username)
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 100:
        raise ValueError("Le nom est obligatoire et ne peut pas dépasser 100 caractères.")
    normalized_prenom = prenom.strip() or None if prenom else None
    if normalized_prenom and len(normalized_prenom) > 100:
        raise ValueError("Le prénom ne peut pas dépasser 100 caractères.")
    normalized_email = email.strip() or None
    if normalized_email and len(normalized_email) > 100:
        raise ValueError("L’adresse e-mail ne peut pas dépasser 100 caractères.")
    if password is not None:
        validate_password(password)
    return normalized_username, normalized_name, normalized_email, normalized_prenom


def _read_database_settings():
    try:
        configured = st.secrets["postgres"]
    except (KeyError, FileNotFoundError) as error:
        raise AuthenticationConfigurationError(
            "Configuration PostgreSQL absente. Copiez "
            ".streamlit/secrets.toml.example vers .streamlit/secrets.toml, puis renseignez "
            "les identifiants."
        ) from error

    required = ("host", "port", "dbname", "user", "password")
    missing = [key for key in required if not configured.get(key)]
    if missing:
        raise AuthenticationConfigurationError(
            "Paramètres PostgreSQL manquants dans [postgres] : " + ", ".join(missing)
        )
    if configured["password"] == "REPLACE_WITH_DATABASE_PASSWORD":
        raise AuthenticationConfigurationError(
            "Remplacez le mot de passe PostgreSQL d’exemple dans "
            ".streamlit/secrets.toml."
        )

    try:
        port = int(configured["port"])
    except (TypeError, ValueError) as error:
        raise AuthenticationConfigurationError(
            "Le port PostgreSQL doit être un nombre entier dans [postgres]."
        ) from error
    return {
        "host": configured["host"],
        "port": port,
        "dbname": configured["dbname"],
        "user": configured["user"],
        "password": configured["password"],
        "sslmode": configured.get("sslmode", "prefer"),
    }


def _read_bootstrap_admin():
    try:
        configured = st.secrets["bootstrap_admin"]
        username = validate_username(configured["username"])
        password = configured["password"]
    except (KeyError, FileNotFoundError) as error:
        raise AuthenticationConfigurationError(
            "Le compte administrateur initial doit être renseigné dans "
            "[bootstrap_admin] de .streamlit/secrets.toml."
        ) from error
    except ValueError as error:
        raise AuthenticationConfigurationError(
            "Le nom d’utilisateur administrateur initial n’est pas valide."
        ) from error

    if not password or password == "REPLACE_WITH_A_LONG_RANDOM_PASSWORD":
        raise AuthenticationConfigurationError(
            "Choisissez un mot de passe initial fort dans [bootstrap_admin] de "
            ".streamlit/secrets.toml."
        )
    if len(password) < 12:
        raise AuthenticationConfigurationError(
            "Le mot de passe administrateur initial doit contenir au moins 12 caractères."
        )
    return username, password


def initialize_database(database_settings):
    with psycopg.connect(**database_settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS roles (
                    id INT PRIMARY KEY,
                    nom_role VARCHAR(50) NOT NULL
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO roles (id, nom_role)
                VALUES (1, 'user'), (2, 'admin')
                ON CONFLICT (id) DO NOTHING
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username VARCHAR(50) PRIMARY KEY,
                    nom VARCHAR(100) NOT NULL,
                    prenom VARCHAR(100),
                    email VARCHAR(100),
                    password VARCHAR(255) NOT NULL,
                    role_id INT NOT NULL REFERENCES roles(id),
                    actif BOOLEAN NOT NULL DEFAULT TRUE
                )
                """
            )
            cursor.execute(
                """
                SELECT
                    EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = 'users' AND column_name = 'login'
                    ),
                    EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = 'users' AND column_name = 'username'
                    )
                """
            )
            has_login, has_username = cursor.fetchone()
            if has_login and not has_username:
                cursor.execute("ALTER TABLE users RENAME COLUMN login TO username")
            elif has_login and has_username:
                raise AuthenticationConfigurationError(
                    "Le schéma users contient simultanément les colonnes login et username. "
                    "Résolvez cette incohérence avant de démarrer l’application."
                )
            cursor.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS prenom VARCHAR(100)"
            )
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = 'weedsgalore_users'
                )
                """
            )
            legacy_exists = cursor.fetchone()[0]
            if legacy_exists:
                cursor.execute(
                    """
                    SELECT username, password_salt, password_hash, role
                    FROM weedsgalore_users
                    """
                )
                legacy_users = cursor.fetchall()
                for username, salt, password_hash, role in legacy_users:
                    if len(username) > 50:
                        raise AuthenticationConfigurationError(
                            "Le compte historique {!r} dépasse la limite de 50 caractères "
                            "du nouveau champ username.".format(username)
                        )
                    encoded_hash = encode_password_hash(
                        bytes(salt), bytes(password_hash), PASSWORD_ITERATIONS
                    )
                    role_id = 2 if role == "admin" else 1
                    cursor.execute(
                        """
                        INSERT INTO users (username, nom, password, role_id, actif)
                        VALUES (%s, %s, %s, %s, TRUE)
                        ON CONFLICT (username) DO NOTHING
                        """,
                        (username, username, encoded_hash, role_id),
                    )

            cursor.execute(
                "SELECT id FROM roles WHERE nom_role = 'admin' ORDER BY id LIMIT 1"
            )
            admin_role = cursor.fetchone()
            cursor.execute(
                "SELECT id FROM roles WHERE nom_role = 'user' ORDER BY id LIMIT 1"
            )
            user_role = cursor.fetchone()
            if admin_role is None or user_role is None:
                raise AuthenticationConfigurationError(
                    "Les rôles 'admin' et 'user' doivent exister dans la table roles."
                )
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM users WHERE role_id = %s AND actif = TRUE)",
                (admin_role[0],),
            )
            has_admin = cursor.fetchone()[0]
            if not has_admin:
                username, password = _read_bootstrap_admin()
                encoded_hash = hash_password(password)
                cursor.execute(
                    """
                    INSERT INTO users (username, nom, password, role_id, actif)
                    VALUES (%s, %s, %s, %s, TRUE)
                    ON CONFLICT (username) DO UPDATE
                    SET role_id = EXCLUDED.role_id,
                        actif = TRUE
                    """,
                    (username, username, encoded_hash, admin_role[0]),
                )


def authenticate(database_settings, username, password):
    normalized_username = username.strip()
    with psycopg.connect(**database_settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.username, u.nom, u.role_id, r.nom_role, u.password
                FROM users AS u
                JOIN roles AS r ON r.id = u.role_id
                WHERE u.username = %s AND u.actif = TRUE
                """,
                (normalized_username,),
            )
            row = cursor.fetchone()

    if row is None or not verify_password(password, row[4]):
        return None
    return {
        "username": row[0],
        "login": row[0],
        "nom": row[1],
        "role_id": row[2],
        "role": row[3],
    }


def list_roles(database_settings):
    with psycopg.connect(**database_settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, nom_role FROM roles ORDER BY nom_role"
            )
            return cursor.fetchall()


def list_users(database_settings):
    with psycopg.connect(**database_settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.username, u.nom, u.prenom, u.email, u.role_id, r.nom_role, u.actif
                FROM users AS u
                JOIN roles AS r ON r.id = u.role_id
                ORDER BY u.username
                """
            )
            return cursor.fetchall()


def create_user(
    database_settings, username, name, email, password, role_id, active=True, prenom=None
):
    (
        normalized_username,
        normalized_name,
        normalized_email,
        normalized_prenom,
    ) = validate_user_fields(username, name, email, password, prenom)
    encoded_hash = hash_password(password)
    with psycopg.connect(**database_settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (username, nom, prenom, email, password, role_id, actif)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    normalized_username,
                    normalized_name,
                    normalized_prenom,
                    normalized_email,
                    encoded_hash,
                    role_id,
                    active,
                ),
            )
    return normalized_username


def update_user(
    database_settings,
    username,
    name,
    email,
    role_id,
    active,
    new_password=None,
    current_username=None,
    prenom=None,
):
    (
        normalized_username,
        normalized_name,
        normalized_email,
        normalized_prenom,
    ) = validate_user_fields(username, name, email, new_password, prenom)
    if new_password:
        password_sql = ", password = %s"
        password_value = hash_password(new_password)
    else:
        password_sql = ""
        password_value = None

    with psycopg.connect(**database_settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM roles WHERE id = %s", (role_id,))
            if cursor.fetchone() is None:
                raise ValueError("Le rôle sélectionné n’existe pas.")
            cursor.execute(
                """
                SELECT r.id
                FROM users AS u
                JOIN roles AS r ON r.id = u.role_id
                WHERE u.username = %s AND r.nom_role = 'admin' AND u.actif = TRUE
                FOR UPDATE OF u
                """,
                (normalized_username,),
            )
            was_active_admin = cursor.fetchone() is not None
            cursor.execute("SELECT nom_role FROM roles WHERE id = %s", (role_id,))
            will_be_active_admin = cursor.fetchone()[0] == "admin" and active
            if (
                normalized_username == current_username
                and not will_be_active_admin
            ):
                raise ValueError(
                    "Vous ne pouvez pas désactiver ou rétrograder votre propre compte admin."
                )
            if was_active_admin and not will_be_active_admin:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM users AS u
                    JOIN roles AS r ON r.id = u.role_id
                    WHERE r.nom_role = 'admin' AND u.actif = TRUE
                    """
                )
                if cursor.fetchone()[0] <= 1:
                    raise ValueError(
                        "Impossible de désactiver ou rétrograder le dernier administrateur actif."
                    )
            cursor.execute(
                """
                UPDATE users
                SET nom = %s, prenom = %s, email = %s, role_id = %s, actif = %s
                """ + password_sql + """
                WHERE username = %s
                """,
                (
                    (
                        normalized_name,
                        normalized_prenom,
                        normalized_email,
                        role_id,
                        active,
                    )
                    + ((password_value,) if new_password else ())
                    + (normalized_username,)
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError("Le compte à modifier n’existe plus.")
    return normalized_username


def delete_user(database_settings, username, current_username=None):
    if username == current_username:
        raise ValueError("Vous ne pouvez pas supprimer votre propre compte.")
    with psycopg.connect(**database_settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.nom_role, u.actif
                FROM users AS u
                JOIN roles AS r ON r.id = u.role_id
                WHERE u.username = %s
                FOR UPDATE OF u
                """,
                (username,),
            )
            target = cursor.fetchone()
            if target is None:
                return False
            if target[0] == "admin" and target[1]:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM users AS u
                    JOIN roles AS r ON r.id = u.role_id
                    WHERE r.nom_role = 'admin' AND u.actif = TRUE
                    """
                )
                if cursor.fetchone()[0] <= 1:
                    raise ValueError("Impossible de supprimer le dernier administrateur actif.")
            cursor.execute("DELETE FROM users WHERE username = %s", (username,))
    return True


def get_authenticated_user(database_settings, username):
    with psycopg.connect(**database_settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.username, u.nom, u.role_id, r.nom_role
                FROM users AS u
                JOIN roles AS r ON r.id = u.role_id
                WHERE u.username = %s AND u.actif = TRUE
                """,
                (username,),
            )
            row = cursor.fetchone()
    if row is None:
        return None
    return {
        "username": row[0],
        "login": row[0],
        "nom": row[1],
        "role_id": row[2],
        "role": row[3],
    }


def render_authentication():
    try:
        database_settings = _read_database_settings()
    except AuthenticationConfigurationError as error:
        st.title("Connexion à WeedsGalore")
        st.error(str(error))
        return None

    if st.session_state.get("_auth_schema_version") != 4:
        try:
            initialize_database(database_settings)
        except AuthenticationConfigurationError as error:
            st.title("Connexion à WeedsGalore")
            st.error(str(error))
            return None
        except psycopg.Error:
            st.title("Connexion à WeedsGalore")
            st.error(
                "Connexion à PostgreSQL impossible. Vérifiez le serveur, la base et les "
                "identifiants dans .streamlit/secrets.toml."
            )
            return None
        st.session_state["_auth_schema_version"] = 4

    current_user = st.session_state.get("authenticated_user")
    if current_user is not None:
        try:
            current_user = get_authenticated_user(
                database_settings,
                current_user.get("username", current_user.get("login", "")),
            )
        except psycopg.Error:
            st.title("Connexion à WeedsGalore")
            st.error("Impossible de vérifier l’état du compte dans PostgreSQL.")
            return None
        if current_user is None:
            st.session_state.pop("authenticated_user", None)
            st.warning("Ce compte est désactivé ou n’existe plus. Veuillez vous reconnecter.")
            return None
        st.session_state["authenticated_user"] = current_user

    if current_user is None:
        # Style CSS : fusion du conteneur du formulaire et du titre en un seul bloc blanc élégant
        st.markdown(
            """
            <style>
                .brand-panel {
                    background: linear-gradient(135deg, #065f46 0%, #059669 100%);
                    padding: 3rem 2.5rem;
                    border-radius: 12px;
                    color: white;
                    height: 100%;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
                }
                [data-testid="stForm"] {
                    background-color: #ffffff;
                    padding: 2.5rem;
                    border-radius: 12px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
                    border: 1px solid #e5e7eb;
                }
                /* Amélioration de la visibilité des zones de saisie */
                [data-testid="stTextInput"] input {
                    background-color: #f9fafb !important;
                    border: 1px solid #d1d5db !important;
                    border-radius: 8px !important;
                    color: #111827 !important;
                    padding: 0.5rem 0.75rem !important;
                }
                [data-testid="stTextInput"] input:focus {
                    border-color: #059669 !important;
                    box-shadow: 0 0 0 2px rgba(5, 150, 105, 0.2) !important;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        col_left, col_right = st.columns([1.1, 0.9], gap="large")

        with col_left:
            st.markdown(
                """
                <div class="brand-panel">
                    <h1 style="color: white; margin-bottom: 0.5rem; font-size: 2rem;">🌾 WeedsGalore</h1>
                    <h3 style="font-weight: 400; font-size: 1.15rem; margin-top: 0; opacity: 0.95; line-height: 1.4;">
                        Plateforme intelligente d'analyse et de cartographie des adventices par drone.
                    </h3>
                    <p style="margin-top: 1.5rem; opacity: 0.85; font-size: 0.9rem; line-height: 1.5;">
                        Optimisez la gestion de vos parcelles agricoles grâce à la puissance de l'intelligence artificielle multispectrale.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_right:
            # Le titre et le sous-titre sont maintenant directement inclus à l'intérieur du formulaire st.form
            with st.form("login-form"):
                st.markdown(
                    """
                    <h2 style="margin-top: 0; color: #111827; font-size: 1.75rem; margin-bottom: 0.25rem;">Connexion</h2>
                    <p style="color: #6b7280; font-size: 0.95rem; margin-bottom: 1.5rem;">Accédez à votre espace de travail sécurisé</p>
                    """,
                    unsafe_allow_html=True,
                )
                username = st.text_input("Username")
                password = st.text_input("Mot de passe", type="password")
                submitted = st.form_submit_button("Se connecter", type="primary", use_container_width=True)

            if submitted:
                try:
                    current_user = authenticate(database_settings, username, password)
                except psycopg.Error:
                    st.error("Erreur lors de la vérification de la connexion PostgreSQL.")
                    return None
                if current_user is None:
                    st.error("Username ou mot de passe incorrect.")
                    return None
                st.session_state["authenticated_user"] = current_user
                st.rerun()
        return None

    st.sidebar.caption(
        "Connecté : {} ({})".format(current_user["username"], current_user["role"])
    )
    if st.sidebar.button("Se déconnecter", key="logout"):
        st.session_state.pop("authenticated_user", None)
        st.rerun()
    return current_user