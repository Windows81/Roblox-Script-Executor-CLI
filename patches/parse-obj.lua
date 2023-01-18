local function escape_char(c)
	if c == '\n' then
		return '\\n'
	elseif c == '\r' then
		return '\\r'
	elseif c == '\t' then
		return '\\t'
	elseif c == '\b' then
		return '\\b'
	elseif c == '\f' then
		return '\\f'
	elseif c == '"' then
		return '\\"'
	elseif c == '\\' then
		return '\\\\'
	else
		return string.format('\\u{%x}', c:byte())
	end
end

local function repr_str(s)
	return string.format('"%s"', s:gsub('[\000-\031%\\"]', escape_char))
end

-- Returns proper string wrapping for instances
local function obj_name(o)
	local n = o.Name
	if #n == 0 --
	or n:match('[^%w]+') --
	or n:sub(1, 1):match('[^%a]') --
	then return string.format('[%s]', repr_str(n)) end
	return string.format('.%s', n)
end

function get_full(o)
	local lp = game.Players.LocalPlayer
	if not o then return nil end
	local r = {obj_name(o)}
	local p = o.Parent
	while p do
		if p == game then
			table.insert(r, 1, 'game')
			return table.concat(r, '')
		elseif p == lp then
			table.insert(r, 1, 'game.Players.LocalPlayer')
			return table.concat(r, '')
		end
		table.insert(r, 1, obj_name(p))
		p = p.Parent
	end
	table.insert(r, 1, 'NIL')
	return table.concat(r, '')
end

local ARG_REPR_TYPES = { --
	CFrame = true,
	Vector3 = true,
	Vector2 = true,
	Vector3int16 = true,
	Vector2int16 = true,
	UDim2 = true,
}
local SEQ_REPR_TYPES = { --
	ColorSequence = true,
	NumberSequence = true,
}
local SEQ_KEYP_TYPES = { --
	ColorSequenceKeypoint = true,
	NumberSequenceKeypoint = true,
}

function parse(obj, nl, lvl) -- Convert the types into strings
	local typ = typeof(obj)
	local lvl = lvl or 0
	if nl == nil then nl = false end

	if typ == 'string' then
		if lvl == 0 then return obj end
		return repr_str(obj)
	end

	-- Instance:GetFullName() except it's not handicapped
	if typ == 'Instance' then return get_full(obj) end

	if typ == 'table' then
		if lvl > 666 then return 'DEEP_TABLE' end
		local keyed_vals = {}
		local ipair_vals = {}
		local tab = '  '
		local c = 0

		local ws_zer = ' '
		local ws_beg = ' '
		local ws_cat = ' '
		local ws_end = ' '
		local sep = ','
		if nl then
			ws_beg = string.format('\n%s', string.rep(tab, lvl + 1))
			ws_cat = string.format('\n%s', string.rep(tab, lvl + 1))
			ws_end = string.format('\n%s', string.rep(tab, lvl))
			ws_zer = string.format('\n%s', string.rep(tab, lvl))
		end

		for i, o in next, obj do
			c = c + 1

			local o_str
			if o ~= obj then
				o_str = parse(o, nl, lvl + 1)
			else
				o_str = 'THIS_TABLE'
			end

			if c == i then
				table.insert(ipair_vals, string.format('%s%s', o_str, sep))
			else
				local i_str = i ~= obj and parse(i, nl, lvl + 1) or 'THIS_TABLE'
				table.insert(keyed_vals, string.format('[%s] = %s%s', i_str, o_str, sep))
			end
		end

		-- Merges keyed values with ipair values - in that order.
		table.sort(keyed_vals)
		table.move(ipair_vals, 1, #ipair_vals, #keyed_vals + 1, keyed_vals)
		if #keyed_vals == 0 then return string.format('{%s}', ws_zer) end

		local all_str = table.concat(keyed_vals, ws_cat)
		return string.format('{%s%s%s}', ws_beg, all_str, ws_end)
	end

	if ARG_REPR_TYPES[typ] then
		local f_args = {typ, tostring(obj):gsub('[{}]', '')}
		return string.format('%s.new(%s)', unpack(f_args))
	end

	if SEQ_REPR_TYPES[typ] then
		local f_args = {typ, parse(obj.Keypoints, nl, lvl)}
		return string.format('%s.new(%s)', unpack(f_args))
	end

	if SEQ_KEYP_TYPES[typ] then
		local f_args = {typ, obj.Time, parse(obj.Value, nl, lvl)}
		return string.format('%s.new(%s, %s)', unpack(f_args))
	end

	if typ == 'Color3' then
		local f_args = {typ, obj.R * 255, obj.G * 255, obj.B * 255}
		return string.format('%s.fromRGB(%d, %d, %d)', unpack(f_args))
	end

	if typ == 'NumberRange' then
		local f_args = {typ, tostring(obj.Min), tostring(obj.Max)}
		return string.format('%s.new(%s, %s)', unpack(f_args))
	end

	if typ == 'userdata' then
		local res
		local meta = getrawmetatable(obj)
		local m_ts = meta and meta.__tostring
		-- Remove __tostring fields to counter traps.
		if m_ts then
			setreadonly(meta, false)
			meta.__tostring = nil
			res = tostring(obj)
			rawset(meta, '__tostring', m_ts)
			setreadonly(meta, rawget(meta, '__metatable') ~= nil)
		else
			res = tostring(obj)
		end
		return res
	end

	return tostring(obj)
end
