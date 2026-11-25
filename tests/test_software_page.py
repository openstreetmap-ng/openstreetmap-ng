async def test_software_directory(client):
    response = await client.get('/software?platform=android&category=navigation')
    assert response.status_code == 200
    assert 'Organic Maps' in response.text
    assert 'StreetComplete' not in response.text
    assert 'method=GET' in response.text or 'method="GET"' in response.text


async def test_software_directory_unknown_filter(client):
    response = await client.get('/software?platform=unknown')
    assert response.status_code == 200
    assert 'JOSM' in response.text
    assert 'Organic Maps' in response.text
