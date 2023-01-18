local rem = game.ReplicatedStorage.HDAdminClient.Signals.RequestCommand
function hd_cmd(cmd) rem:InvokeServer(cmd) end
