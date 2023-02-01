local rs = game:GetService 'ReplicatedStorage'
local rem = rs.HDAdminClient.Signals.RequestCommand
function hd_cmd(cmd) rem:InvokeServer(cmd) end
