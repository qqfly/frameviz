use crate::host::HostError;
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;

#[derive(Clone, Debug, Serialize)]
pub(crate) struct Widget {
    id: String,
    kind: String,
    label: String,
    parent: Option<String>,
    value: Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    minimum: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    maximum: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    step: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    choices: Option<Vec<String>>,
    update_mode: String,
}

fn invalid(message: &str) -> HostError {
    HostError::new("ERR_INVALID_ARGS", message)
}

fn required_string<'a>(args: &'a Value, key: &str) -> Result<&'a str, HostError> {
    args.get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", format!("{key} must be a string")))
}

fn optional_number(args: &Value, key: &str) -> Result<Option<f64>, HostError> {
    args.get(key)
        .map(|value| {
            value
                .as_f64()
                .filter(|v| v.is_finite())
                .ok_or_else(|| HostError::new("ERR_INVALID_ARGS", format!("{key} must be finite")))
        })
        .transpose()
}

impl Widget {
    fn validate_value(&self, value: &Value) -> Result<(), HostError> {
        let valid = match self.kind.as_str() {
            "number" => value.as_f64().is_some_and(|v| {
                v.is_finite()
                    && self.minimum.is_none_or(|min| v >= min)
                    && self.maximum.is_none_or(|max| v <= max)
            }),
            "checkbox" => value.is_boolean(),
            "select" => value.as_str().is_some_and(|v| {
                self.choices
                    .as_ref()
                    .is_some_and(|choices| choices.iter().any(|choice| choice == v))
            }),
            "text_input" | "text" => value.is_string(),
            "button" | "group" => value.is_null(),
            _ => false,
        };
        if valid {
            Ok(())
        } else {
            Err(invalid("Value does not match widget type or range"))
        }
    }
}

#[derive(Default)]
pub(crate) struct Widgets {
    counter: u64,
    scenes: BTreeMap<String, BTreeMap<u64, Widget>>,
}

impl Widgets {
    pub fn list(&self, scene: &str) -> Vec<&Widget> {
        self.scenes
            .get(scene)
            .into_iter()
            .flat_map(|widgets| widgets.values())
            .collect()
    }

    pub fn destroy_scene(&mut self, scene: &str) {
        self.scenes.remove(scene);
    }

    fn find(&self, scene: &str, id: &str) -> Result<u64, HostError> {
        id.strip_prefix("w_")
            .and_then(|v| v.parse::<u64>().ok())
            .filter(|index| {
                self.scenes
                    .get(scene)
                    .and_then(|widgets| widgets.get(index))
                    .is_some_and(|widget| widget.id == id)
            })
            .ok_or_else(|| HostError::new("ERR_NOT_FOUND", "Widget is not in this scene"))
    }

    pub fn add(&mut self, scene: &str, args: &Value) -> Result<Value, HostError> {
        let kind = required_string(args, "kind")?;
        if !matches!(
            kind,
            "number" | "checkbox" | "select" | "text_input" | "button" | "text" | "group"
        ) {
            return Err(invalid("Unknown widget kind"));
        }
        let label = required_string(args, "label")?;
        let parent = match args.get("parent") {
            None | Some(Value::Null) => None,
            Some(value) => {
                let id = value
                    .as_str()
                    .ok_or_else(|| invalid("parent must be a widget ID"))?;
                let index = self.find(scene, id)?;
                if self.scenes[scene][&index].kind != "group" {
                    return Err(invalid("Widget parent must be a group"));
                }
                Some(id.to_string())
            }
        };
        let update_mode = args
            .get("update_mode")
            .map_or(Some("commit"), Value::as_str)
            .filter(|v| *v == "commit" || (*v == "continuous" && kind == "number"))
            .ok_or_else(|| invalid("update_mode must be commit or continuous for a number"))?;
        let (minimum, maximum, step) = (
            optional_number(args, "minimum")?,
            optional_number(args, "maximum")?,
            optional_number(args, "step")?,
        );
        if kind != "number" && (minimum.is_some() || maximum.is_some() || step.is_some()) {
            return Err(invalid("Number range options require a number widget"));
        }
        if matches!((minimum, maximum), (Some(a), Some(b)) if a >= b)
            || step.is_some_and(|v| v <= 0.0)
        {
            return Err(invalid(
                "Widget range must increase and step must be positive",
            ));
        }
        let choices = if kind == "select" {
            let options: Vec<String> = serde_json::from_value(args["choices"].clone())
                .map_err(|_| invalid("Select choices must be strings"))?;
            if options.is_empty()
                || options
                    .iter()
                    .collect::<std::collections::HashSet<_>>()
                    .len()
                    != options.len()
            {
                return Err(invalid("Select choices must be nonempty and unique"));
            }
            Some(options)
        } else {
            if args.get("choices").is_some() {
                return Err(invalid("choices requires a select widget"));
            }
            None
        };
        let index = self.counter + 1;
        let widget = Widget {
            id: format!("w_{index}"),
            kind: kind.to_string(),
            label: label.to_string(),
            parent,
            value: args["value"].clone(),
            minimum,
            maximum,
            step,
            choices,
            update_mode: update_mode.to_string(),
        };
        widget.validate_value(&widget.value)?;
        let result = json!({"widget": widget});
        self.scenes
            .entry(scene.to_string())
            .or_default()
            .insert(index, widget);
        self.counter = index;
        Ok(result)
    }

    pub fn get(&self, scene: &str, args: &Value) -> Result<Value, HostError> {
        let index = self.find(scene, required_string(args, "widget_id")?)?;
        Ok(json!({"widget": self.scenes[scene][&index]}))
    }

    pub fn set(&mut self, scene: &str, args: &Value) -> Result<Value, HostError> {
        let index = self.find(scene, required_string(args, "widget_id")?)?;
        let widget = self.scenes.get_mut(scene).unwrap().get_mut(&index).unwrap();
        let value = args
            .get("value")
            .ok_or_else(|| invalid("value is required"))?;
        let user = args["source"].as_str() == Some("user");
        if widget.kind == "group" || (user && widget.kind == "text") {
            return Err(invalid("Widget cannot be edited by this command"));
        }
        let emit = args
            .get("emit")
            .map_or(Some(false), Value::as_bool)
            .ok_or_else(|| invalid("emit must be a boolean"))?;
        let phase = args
            .get("phase")
            .map_or(Some("commit"), Value::as_str)
            .filter(|phase| {
                *phase == "commit"
                    || (*phase == "input" && user && widget.update_mode == "continuous")
            })
            .ok_or_else(|| invalid("Invalid widget phase for this update mode"))?;
        widget.validate_value(value)?;
        widget.value = value.clone();
        let event = (user || emit).then(|| {
            json!({
                "scene_id": scene, "view_id": args["view_id"], "widget_id": widget.id,
                "value": value, "source": if user { "user" } else { "program" }, "phase": phase,
            })
        });
        Ok(json!({"widget": widget, "event": event}))
    }

    pub fn remove(&mut self, scene: &str, args: &Value) -> Result<Value, HostError> {
        let index = self.find(scene, required_string(args, "widget_id")?)?;
        let widgets = self.scenes.get_mut(scene).unwrap();
        let mut removed = vec![widgets.remove(&index).unwrap().id];
        // Parent IDs are assigned before their children.
        widgets.retain(|_, widget| {
            if widget
                .parent
                .as_ref()
                .is_some_and(|id| removed.contains(id))
            {
                removed.push(widget.id.clone());
                false
            } else {
                true
            }
        });
        Ok(json!({"removed": removed}))
    }
}
