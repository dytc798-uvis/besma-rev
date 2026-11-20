using Mono.Cecil;
using Mono.Cecil.Cil;
using System.Security.Cryptography;
using System.Text.Json;
if(args.Length!=3)throw new Exception("baseline donor output");
if(Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[0]))).ToLowerInvariant()!="3d046bd756c111f2db066632e4364971e28c010e2d46c03c44038f17e869870c")throw new Exception("EXACT_CURRENT_REQUIRED");
using var baseline=AssemblyDefinition.ReadAssembly(args[0]);using var donor=AssemblyDefinition.ReadAssembly(args[1]);var m=baseline.MainModule;
var before=All(m).ToDictionary(x=>x.FullName,Print);
var origin=donor.MainModule.Types.Single(t=>t.Name=="PeriodLines");var source=origin.Methods.Single(x=>x.Name=="Decorate");
var type=new TypeDefinition(origin.Namespace,origin.Name,origin.Attributes,m.TypeSystem.Object);m.Types.Add(type);
var method=new MethodDefinition(source.Name,source.Attributes,m.ImportReference(source.ReturnType));type.Methods.Add(method);
foreach(var p in source.Parameters)method.Parameters.Add(new ParameterDefinition(p.Name,p.Attributes,m.ImportReference(p.ParameterType)));
method.Body=new MethodBody(method){InitLocals=source.Body.InitLocals,MaxStackSize=source.Body.MaxStackSize};
var vars=source.Body.Variables.ToDictionary(v=>v,v=>new VariableDefinition(m.ImportReference(v.VariableType)));foreach(var v in vars.Values)method.Body.Variables.Add(v);
var ins=source.Body.Instructions.ToDictionary(i=>i,i=>Instruction.Create(OpCodes.Nop));
foreach(var i in source.Body.Instructions){var c=ins[i];c.OpCode=i.OpCode;c.Operand=i.Operand switch{null=>null,Instruction b=>ins[b],Instruction[] bs=>bs.Select(b=>ins[b]).ToArray(),VariableDefinition v=>vars[v],ParameterDefinition p=>method.Parameters[p.Index],MethodReference mr=>m.ImportReference(mr),FieldReference f=>m.ImportReference(f),TypeReference t=>m.ImportReference(t),_=>i.Operand};method.Body.Instructions.Add(c);}
foreach(var h in source.Body.ExceptionHandlers)method.Body.ExceptionHandlers.Add(new ExceptionHandler(h.HandlerType){TryStart=ins[h.TryStart],TryEnd=h.TryEnd is null?null:ins[h.TryEnd],HandlerStart=ins[h.HandlerStart],HandlerEnd=h.HandlerEnd is null?null:ins[h.HandlerEnd],CatchType=h.CatchType is null?null:m.ImportReference(h.CatchType),FilterStart=h.FilterStart is null?null:ins[h.FilterStart]});
var target=All(m).Single(x=>x.DeclaringType.FullName=="SafetyTeamDesk.MainWindow"&&x.Name=="BuildDayCell");
if(target.Parameters.Count!=3||target.ReturnType.FullName!="System.Windows.Controls.Border")throw new Exception("CELL_SIGNATURE_CHANGED");
var il=target.Body.GetILProcessor();foreach(var ret in target.Body.Instructions.Where(x=>x.OpCode==OpCodes.Ret).ToArray()){il.InsertBefore(ret,Instruction.Create(OpCodes.Ldarg_1));il.InsertBefore(ret,Instruction.Create(OpCodes.Call,method));}
target.Body.MaxStackSize+=2;
var changed=new HashSet<string>{target.FullName};int anchors=0;
foreach(var f in All(m).Where(x=>x.HasBody))foreach(var i in f.Body.Instructions)if(i.OpCode==OpCodes.Ldstr&&i.Operand is string s&&s.Contains("team1a23.1-meaningful-editor-changes")){i.Operand=s.Replace("team1a23.1-meaningful-editor-changes","team1a23.3-period-calendar");changed.Add(f.FullName);anchors++;}
if(anchors==0)throw new Exception("VISIBLE_VERSION_REQUIRED");
foreach(var a in baseline.CustomAttributes){if(a.AttributeType.FullName=="System.Reflection.AssemblyFileVersionAttribute")a.ConstructorArguments[0]=new CustomAttributeArgument(m.TypeSystem.String,"1.0.23.3");if(a.AttributeType.FullName=="System.Reflection.AssemblyInformationalVersionAttribute")a.ConstructorArguments[0]=new CustomAttributeArgument(m.TypeSystem.String,"team1a23.3-period-calendar");}
baseline.Write(args[2]);using var output=AssemblyDefinition.ReadAssembly(args[2]);var after=All(output.MainModule).ToDictionary(x=>x.FullName,Print);
foreach(var p in before)if(!changed.Contains(p.Key)&&after[p.Key]!=p.Value)throw new Exception("UNRELATED_METHOD_CHANGED "+p.Key);
if(after.Count!=before.Count+1||baseline.Name.Version!=output.Name.Version)throw new Exception("IDENTITY_CHANGED");
foreach(var r in m.Resources.OfType<EmbeddedResource>())if(!r.GetResourceData().SequenceEqual(output.MainModule.Resources.OfType<EmbeddedResource>().Single(x=>x.Name==r.Name).GetResourceData()))throw new Exception("RESOURCE_CHANGED");
if(output.MainModule.AssemblyReferences.Any(x=>x.Name=="Decorate"))throw new Exception("DONOR_REFERENCE");
Console.WriteLine(JsonSerializer.Serialize(new{passed=true,original_methods_preserved=before.Count-changed.Count,resources_preserved=m.Resources.Count,version="1.0.23.3",sha256=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[2]))).ToLowerInvariant()}));
static IEnumerable<TypeDefinition> Types(TypeDefinition t)=>new[]{t}.Concat(t.NestedTypes.SelectMany(Types));
static IEnumerable<MethodDefinition> All(ModuleDefinition m)=>m.Types.SelectMany(Types).SelectMany(t=>t.Methods);
static string Print(MethodDefinition x)=>x.HasBody?string.Join("|",x.Body.Instructions.Select(i=>i.OpCode.Code+":"+(i.Operand switch{Instruction b=>x.Body.Instructions.IndexOf(b).ToString(),Instruction[] bs=>string.Join(",",bs.Select(b=>x.Body.Instructions.IndexOf(b))),_=>i.Operand?.ToString()}))):"no-body";
