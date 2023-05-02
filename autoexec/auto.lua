-- Script paths that are automatically loaded once injected.
local SCRIPTS = {
	'hop.lua',
	'zoom-dist.lua',
	'far-click.lua',
	'tele-key.lua',
	'locale.lua',
	-- 'fly.lua',
	-- 'auto-rejoin.lua',
	-- 'mute.lua',
	-- 'country.lua',
	-- 'anti-kick.lua',
	-- 'rspy.lua',
	'anti-afk.lua',
	'event-log.lua',
}

-- Returns a list of paths to search given the command query.
local function path_list(n, ...)
	if type(n) == 'number' then
		return { --
			('place/%011d-.lua'):format(n),
			('place/%011d.lua'):format(n),
		}
	end

	local l = n:lower()
	local _, _, id, suffix = l:find('^([0-9]+)(.*)$')
	if not id then
		_, _, suffix = l:find('^place(.*)$')
		id = game.PlaceId
	end

	if suffix == '-' then
		return { --
			('place/%011d-.lua'):format(id),
			('place/%011d.lua'):format(id),
		}
	elseif suffix == '+' then
		return { --
			('place/%011d.lua'):format(id),
		}
	elseif suffix == '' then
		return { --
			('place/%011d-.lua'):format(id),
		}
	end

	if l ~= n then
		return { --
			string.format('%s.lua', n),
			string.format('%s.lua', l),
			n,
			l,
		}
	else
		return { --
			string.format('%s.lua', n),
			n,
		}
	end
end

local function find_path(n, ...)
	for _, f in next, path_list(n, ...) do if f and isfile(f) then return f end end
end

local NOT_FOUND_STRING = 'QUERY "%s" DID NOT YIELD ANY RESULTS'
local function exec(n, ...)
	local path = find_path(n, ...)
	if not path then error(string.format(NOT_FOUND_STRING, n)) end
	_E.ARGS = {...}
	_E.OUTPUT = nil
	local result = {loadfile(path)()}
	_E.ARGS = nil
	_E.RETURN = result
	return unpack(result)
end

local function output(o)
	loadfile('save.lua')(_E.OUT_PATH, o, true)
	return o
end

local env = getrenv()
local BASE = { --
	RSEXEC = exec,
	FIND_PATH = find_path,
	PATH_LIST = path_list,
	OUTPUT = output,
}
local ALIASES = { --
	['R'] = 'RETURN',
	['E'] = 'RSEXEC',
	['F'] = 'FIND_PATH',
	['L'] = 'PATH_LIST',
	['A'] = 'ARGS',
	['O'] = 'OUTPUT',
	['EXEC'] = 'RSEXEC',
	['FIND'] = 'FIND_PATH',
	['LIST'] = 'PATH_LIST',
}

local function get_meta_key(k)
	local l = k:upper()
	return ALIASES[l] or l
end

env._E = setmetatable(
	BASE, {
		__index = function(self, k) return rawget(self, get_meta_key(k)) end,
		__newindex = function(self, k, v) return rawset(self, get_meta_key(k), v) end,
		__call = function(self, ...) return exec(...) end,
	})

_E.AUTO = true
print('AUTO SCRIPTS READYING!')
for _, n in next, SCRIPTS do
	print('AUTO SCRIPT TO LOAD:', n)
	pcall(loadfile(n))
end

local pl_n = string.format('place/%011d.lua', game.PlaceId)
if isfile(pl_n) then
	print('PLACE SCRIPT TO LOAD:', pl_n)
	pcall(loadfile(pl_n))
end

print('AUTO SCRIPTS ARE DONE!')
_E.AUTO = false
