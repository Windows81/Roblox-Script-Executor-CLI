local function get_servers(place, limit, is_asc)
	local place = place or game.PlaceId
	local order = is_asc and 'Asc' or 'Desc'
	local servers = {}
	local cursor = ''
	local count = 0
	repeat
		local req = game:HttpGet(
			string.format(
				'https://games.roblox.com/v1/games/%s/servers/Public?sortOrder=%s&limit=100&cursor=%s',
					place, order, cursor))
		local iters = {
			id = string.gmatch(req, '"id":"(........%-....%-....%-....%-............)"'),
			playing = string.gmatch(req, '"playing":(%d+)'),
		}
		local function iter(...)
			local ret = {}
			for i, f in next, iters do
				local r = f(...)
				if not r then return nil end
				ret[i] = r
			end
			return ret
		end
		for m in iter do
			count = count + 1
			table.insert(servers, m)
			if count == limit then return servers end
		end
		cursor = string.match(req, '"nextPageCursor":"([^,]+)"')
	until not cursor
	return servers
end
