function infer_plr(pl_ref)
	local to_pl
	local lp = game.Players.LocalPlayer
	if typeof(pl_ref) == 'string' then
		local min = math.huge
		for _, p in next, game.Players:GetPlayers() do
			if p ~= lp then
				local nv = math.huge
				local un = p.Name
				local dn = p.DisplayName

				if un:find('^' .. pl_ref) then
					nv = 1.0 * (#un - #pl_ref)

				elseif dn:find('^' .. pl_ref) then
					nv = 1.5 * (#dn - #pl_ref)

				elseif un:lower():find('^' .. pl_ref:lower()) then
					nv = 2.0 * (#un - #pl_ref)

				elseif dn:lower():find('^' .. pl_ref:lower()) then
					nv = 2.5 * (#dn - #pl_ref)

				end
				if nv < min then
					to_pl = p
					min = nv
				end
			end
		end
		return to_pl
	else
		return pl_ref
	end
end
