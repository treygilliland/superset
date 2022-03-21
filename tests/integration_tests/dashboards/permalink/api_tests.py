# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
import json
from unittest.mock import patch

import pytest
from flask_appbuilder.security.sqla.models import User
from sqlalchemy.orm import Session

from superset import db
from superset.dashboards.commands.exceptions import DashboardAccessDeniedError
from superset.key_value.models import KeyValueEntry
from superset.models.dashboard import Dashboard
from superset.models.slice import Slice
from tests.integration_tests.base_tests import login
from tests.integration_tests.fixtures.client import client
from tests.integration_tests.fixtures.world_bank_dashboard import (
    load_world_bank_dashboard_with_slices,
    load_world_bank_data,
)
from tests.integration_tests.test_app import app

STATE = {
    "filterState": {"FILTER_1": "foo",},
    "hash": "my-anchor",
}


@pytest.fixture
def dashboard_id(load_world_bank_dashboard_with_slices) -> int:
    with app.app_context() as ctx:
        session: Session = ctx.app.appbuilder.get_session
        dashboard = session.query(Dashboard).filter_by(slug="world_health").one()
        return dashboard.id


def test_post(client, dashboard_id: int):
    login(client, "admin")
    resp = client.post(f"api/v1/dashboard/{dashboard_id}/permalink", json=STATE)
    assert resp.status_code == 201
    data = json.loads(resp.data.decode("utf-8"))
    key = data["key"]
    url = data["url"]
    assert key in url
    db.session.query(KeyValueEntry).filter_by(uuid=key).delete()
    db.session.commit()


@patch("superset.security.SupersetSecurityManager.raise_for_dashboard_access")
def test_post_access_denied(mock_raise_for_dashboard_access, client, dashboard_id: int):
    login(client, "admin")
    mock_raise_for_dashboard_access.side_effect = DashboardAccessDeniedError()
    resp = client.post(f"api/v1/dashboard/{dashboard_id}/permalink", json=STATE)
    assert resp.status_code == 403


def test_post_invalid_schema(client, dashboard_id: int):
    login(client, "admin")
    resp = client.post(
        f"api/v1/dashboard/{dashboard_id}/permalink", json={"foo": "bar"}
    )
    assert resp.status_code == 400


def test_get(client, dashboard_id: int):
    login(client, "admin")
    resp = client.post(f"api/v1/dashboard/{dashboard_id}/permalink", json=STATE)
    data = json.loads(resp.data.decode("utf-8"))
    key = data["key"]
    resp = client.get(f"api/v1/dashboard/permalink/{key}")
    assert resp.status_code == 200
    result = json.loads(resp.data.decode("utf-8"))
    assert result["dashboardId"] == str(dashboard_id)
    assert result["state"] == STATE
    db.session.query(KeyValueEntry).filter_by(uuid=key).delete()
    db.session.commit()